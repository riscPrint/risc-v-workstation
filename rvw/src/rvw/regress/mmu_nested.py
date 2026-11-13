"""Independent two-stage translation, including G translation of VS PTE reads."""
from .mmu_walk import walk


class GuestFault(Exception):
    def __init__(self, result, address):
        self.result, self.address = result, address


def translate(*, vs_mode, vs_root, g_mode, g_root, va, access, memory, privilege='S'):
    g_walks = []
    def gtranslate(gpa, operation):
        result = walk(mode=g_mode, root=g_root, va=gpa, access=operation,
                      memory=memory, privilege='U', x4=True)
        g_walks.append(dict(gpa=gpa, access=operation, **result))
        if result['status'] != 'success':
            raise GuestFault(result, gpa)
        return result['pa']
    def read_vs(gpa):
        hpa = gtranslate(gpa, 'load')
        if hpa not in memory:
            raise ValueError(f'missing host memory at {hpa:#x}')
        return memory[hpa]
    vs_walk = None
    try:
        vs_walk = walk(mode=vs_mode, root=vs_root, va=va, access=access,
                       memory={}, privilege=privilege, pte_reader=read_vs)
        if vs_walk['status'] != 'success':
            return dict(status=vs_walk['status'], stage='vs', vs_walk=vs_walk, g_walks=g_walks)
        pa = gtranslate(vs_walk['pa'], access)
        return dict(status='success', pa=pa, vs_walk=vs_walk, g_walks=g_walks)
    except GuestFault as fault:
        return dict(status='guest-page-fault' if fault.result['status'] == 'page-fault' else 'access-fault',
                    stage='g', htval=fault.address >> 2, vs_walk=vs_walk, g_walks=g_walks)
