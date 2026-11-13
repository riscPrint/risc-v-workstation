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


def scenario_accesses(s, source=None):
    """Read declared table words from the generated source, never DUT data."""
    if 'guest_pointer' in s or not s.get('guest') or s.get('guest_op', 'hlv.d') not in ('hlv.d', 'hlvx.wu', 'hsv.d') or 'ad_expect' in s or not {'A', 'D'} <= set(s['flags']):
        return []
    from .mmu import ROOT, number
    from .mmu_hypervisor import assembly
    from .mmu_paging import MODES
    source = (source if source is not None else assembly(s)).split('.section .tables,"aw"\n', 1)[1].split('.section .data', 1)[0]
    address, memory = ROOT, {}
    for line in source.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == '.dword':
            memory[address] = number(fields[1])
            address += 8
        elif fields[0] == '.zero':
            for location in range(address, address + number(fields[1]), 8):
                memory[location] = 0
            address += number(fields[1])
        else:
            raise ValueError('unsupported generated table directive')
    first = dict(vs_mode=s['mode'], vs_root=ROOT, g_mode=s.get('guest_mode', 'sv39'), g_root=0x80020000,
                 va=0x40000000, access=s['access'], memory=memory)
    if s.get('guest_op') == 'hlvx.wu':
        # HLVX uses execute permission in both stages. VS PTE reads remain loads.
        first['access'] = 'fetch'
    if not s.get('guest_switch'):
        return [first]
    g = MODES[first['g_mode']]
    alternate = (first['g_root'] + 16384 + (g.levels - 2) * 4096 + 16383) & -16384
    return [first, dict(first, g_root=alternate), first]


def check(records, accesses):
    from .mmu import number
    def normalize(value, key=None):
        if isinstance(value, dict):
            return {k: normalize(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        return number(value) if key in ('address', 'data', 'pa', 'gpa', 'htval') and value is not None else value
    records, accesses = list(records), list(accesses)
    if not accesses:
        return dict(status='inconclusive', checked=0, expected=0, reason='no supported nested reference accesses')
    errors, complete = [], 0
    for index, (record, access) in enumerate(zip(records, accesses)):
        expected = translate(**access)
        if record.get('access_id') != index:
            errors.append(f'access {index}: wrong nested access_id')
        for field in ('vs_mode', 'g_mode', 'access'):
            if record.get(field) != access[field]:
                errors.append(f'access {index}: wrong {field}')
        for field in ('vs_root', 'g_root', 'va'):
            if number(record.get(field, -1)) != number(access[field]):
                errors.append(f'access {index}: wrong {field}')
        if record.get('complete') is not True:
            continue
        complete += 1
        if normalize(record.get('result')) != expected:
            errors.append(f'access {index}: nested PTE reads or translation result differ')
    if len(records) > len(accesses):
        errors.append('extra nested DUT walks')
    return dict(status='mismatch' if errors else 'consistent' if records and complete == len(records) == len(accesses) else 'inconclusive',
                checked=min(len(records), len(accesses)), expected=len(accesses), errors=errors)


def check_c2(path, scenario, identity, source=None):
    from rvw.cosim.trace import Trace
    trace = Trace(path)
    try:
        if not identity.get('rtl_sha256') or any(k not in trace.header or k not in identity or trace.header[k] != identity[k] for k in ('core', 'config', 'elf_sha256', 'rtl_sha256', 'source', 'seed')):
            return dict(status='inconclusive', reason='nested C2 identity differs from C1')
        records, ended = [], False
        for row in trace:
            if row.get('event') == 'end':
                ended = row.get('status') == 'pass'
            elif 'event' not in row:
                records.extend(row.get('mmu_nested_walks', []))
        if not ended:
            return dict(status='inconclusive', reason='missing passing C2 end')
        return check(records, scenario_accesses(scenario, source))
    finally:
        trace.close()
