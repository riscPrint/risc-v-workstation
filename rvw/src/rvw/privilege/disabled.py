"""Disabled architectural state and absent supervisor operation campaigns."""
from .programs import HEAD, TAIL

BITS = {'sum': 18, 'mxr': 19, 'mprv': 17, 'tvm': 20, 'tw': 21, 'tsr': 22}


def enter(mode):
    return f''' li t0, 0x1800
 csrc mstatus, t0
 li t0, {dict(M=3, S=1, U=0)[mode] << 11}
 csrs mstatus, t0
 la t0, access_site
 csrw mepc, t0
 mret
'''


def programs(config):
    absent = config.get('priv', 'msu') == 'mu'
    if absent:
        modes = ['M', 'U']
        operations = {'satp': 'csrr a0, satp', 'sfence': 'sfence.vma', 'sret': 'sret'}
        head = HEAD.replace(' csrw satp, zero\n', '').replace(' csrw medeleg, zero\n', '').replace(' csrw mideleg, zero\n', '')
    else:
        modes = config.get('modes', ['M', 'S', 'U'])
        if 'f' not in config.get('isa', '').split('_')[0][4:]:
            raise ValueError('FS-disabled campaign requires an ISA with F')
        operations = {'fs-off': 'fmv.w.x f0, zero'}
        head = HEAD
    rows = []
    for mode in modes:
        for control, bit in BITS.items():
            for enabled in (0, 1):
                for operation, instruction in operations.items():
                    ident = f'disabled-{operation}-{control}-{enabled}-{mode.lower()}'
                    assembly = head + f''' la t0, handler
 csrw mtvec, t0
 li t0, 0x6000
 csrc mstatus, t0
 li t0, {1 << bit}
 {'csrs' if enabled else 'csrc'} mstatus, t0
''' + enter(mode) + f'''access_site:
 {instruction}
 j fail
handler:
 csrr t0, mcause
 li t1, 2
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
 j pass
''' + TAIL
                    rows.append(dict(id=ident, family='disabled', bins=[f'disabled.{operation}.{mode}.{control}.{enabled}'], assembly=assembly))
    return rows
