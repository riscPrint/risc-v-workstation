"""Standard PMP: address modes, permissions, locks, priority and MPRV.

Smepmp is deliberately a separate generator. These rows do not count as ePMP.
"""
from .programs import head, tail, xlen
from .disabled import enter


def programs(config):
    rows = []
    options=config.get('pmp',{})
    grain=options.get('granularity_bytes',4)
    if type(grain) is not int or not 4<=grain<=4096 or grain&(grain-1):
        raise ValueError('PMP granularity must be a power of two in 4..4096')
    narrow=xlen(config)==32
    if options.get('entries',8)<(4 if narrow else 8):
        raise ValueError('PMP matrix bootstrap requires eight entries (four on RV32)')
    addressing_modes=options.get('address_modes',['tor','na4','napot'] if grain==4 else ['tor','napot'])
    if not addressing_modes or len(set(addressing_modes))!=len(addressing_modes) or set(addressing_modes)-{'tor','na4','napot'} or ('na4' in addressing_modes and grain!=4):
        raise ValueError('PMP address modes differ from declared granularity')
    modes=config.get('modes', ['M', 'U', 'mprv-u'] if config.get('priv')=='mu' else ['M', 'S', 'U', 'mprv-s', 'mprv-u'])
    if config.get('priv')=='mu' and set(modes)&{'S','mprv-s'}:
        raise ValueError('an M/U core has no S-mode PMP rows')
    for addressing in addressing_modes:
        for mode in modes:
            if mode not in ('M', 'S', 'U', 'mprv-s', 'mprv-u'):
                raise ValueError('unsupported PMP mode')
            for locked in (False, True):
                for access in ('read', 'write', 'execute'):
                    if mode.startswith('mprv') and access == 'execute':
                        continue
                    for permissions in (0, 1, 3, 5, 7):
                        ident = f'pmp-{addressing}-{mode.lower()}-{int(locked)}-{permissions}-{access}'
                        rows.append(dict(id=ident, family='pmp',
                            bins=[f'pmp.{addressing}.{mode}.{int(locked)}.{permissions}.{access}'],
                            assembly=program(addressing, mode, locked, permissions, access, grain=grain, config=config)))
    for mode in (m for m in modes if m!='M'):
        rows.append(dict(id='pmp-priority-' + mode, family='pmp', bins=['pmp.priority.' + mode],
            assembly=program('napot', mode, False, 7, 'read', priority=True, grain=grain, config=config)))
    return rows


def program(addressing, mode, locked, permissions, access, priority=False, grain=4, config=None):
    config = config or {}
    # The allow-all TOR fallback is the last entry of pmpcfg0: entry 7 on RV64,
    # entry 3 on RV32 (pmpcfg0 holds four entries there). Its base entry is zero.
    last = 3 if xlen(config) == 32 else 7
    slot = int(addressing == 'tor' or priority)
    size = 4 if addressing == 'na4' else max(16,grain)
    cfg = {'tor': 8, 'na4': 16, 'napot': 24}[addressing] | permissions | (128 if locked else 0)
    value = (15 << (8 * last)) | (cfg << (8 * slot)) | (24 if priority else 0)
    lower = mode != 'M'
    denied = (not (permissions & {'read': 1, 'write': 2, 'execute': 4}[access]) and (lower or locked)) or priority
    physical = 'M' if mode.startswith('mprv') else mode
    text = head(config) + f''' csrw pmpcfg0, zero
 csrw pmpaddr{last - 1}, zero
 la t0, handler
 csrw mtvec, t0
 la t0, test_area
 srli t0, t0, 2
'''
    if addressing == 'tor':
        text += f' csrw pmpaddr0, t0\n addi t0, t0, {size//4}\n'
    elif addressing == 'napot':
        text += f' ori t0, t0, {size//8-1}\n'
    if priority:
        text += ' csrw pmpaddr0, t0\n'
    text += f''' csrw pmpaddr{slot}, t0
 mv s3, t0
 li t0, -1
 csrw pmpaddr{last}, t0
 li t0, {value}
 csrw pmpcfg0, t0
'''
    if locked:
        text += f''' li t0, {15 << (8 * last)}
 csrw pmpcfg0, t0
 csrr t0, pmpcfg0
 srli t0, t0, {8 * slot}
 andi t0, t0, 255
 li t1, {cfg}
 bne t0, t1, fail
 csrw pmpaddr{slot}, zero
 csrr t0, pmpaddr{slot}
 bne t0, s3, fail
'''
        if addressing == 'tor':
            text += ''' csrr s4, pmpaddr0
 csrw pmpaddr0, zero
 csrr t0, pmpaddr0
 bne t0, s4, fail
'''
    text += enter(physical)
    mprv = ''
    if mode.startswith('mprv'):
        mprv = f''' li t0, 0x1800
 csrc mstatus, t0
 li t0, {0x20000 | (0x800 if mode == 'mprv-s' else 0)}
 csrs mstatus, t0
'''
    text += 'access_site:\n' + mprv + ''' la a0, test_area
 li a1, 43
access_op:
'''
    text += {'read': ' lw a1, 0(a0)\n li t0, 42\n bne a1, t0, fail\n',
             'write': ' sw a1, 0(a0)\n', 'execute': ' jr a0\n'}[access]
    text += f'''after_access:
ecall_site:
 ecall
 j fail
handler:
 csrr t0, mcause
 li t1, {({'read': 5, 'write': 7, 'execute': 1}[access] if denied else {'M': 11, 'S': 9, 'U': 8}[physical])}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {('test_area' if access == 'execute' else 'access_op') if denied else 'ecall_site'}
 bne t0, t1, fail
'''
    if denied:
        text += ''' csrr t0, mtval
 la t1, test_area
 bne t0, t1, fail
'''
    elif access == 'write':
        # Permissions include R when W is set. Verify the store independently.
        text += ''' la t0, test_area
 lw t0, 0(t0)
 li t1, 43
 bne t0, t1, fail
'''
    text += ' j pass\n' + tail(config) + f'''.section .probe,"awx"
.balign {size}
.globl test_area
test_area:
'''
    text += ' j after_access\n .word 0\n' if access == 'execute' else ' .word 42, 0\n'
    text += ' .dword 0\n'
    return text
