"""Standard PMP: address modes, permissions, locks, priority and MPRV.

Smepmp is deliberately a separate generator. These rows do not count as ePMP.
"""
from .programs import HEAD, TAIL
from .disabled import enter


def programs(config):
    rows = []
    for addressing in ('tor', 'na4', 'napot'):
        for mode in config.get('modes', ['M', 'S', 'U', 'mprv-s', 'mprv-u']):
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
                            assembly=program(addressing, mode, locked, permissions, access)))
    for mode in ('S', 'U', 'mprv-s', 'mprv-u'):
        rows.append(dict(id='pmp-priority-' + mode, family='pmp', bins=['pmp.priority.' + mode],
            assembly=program('napot', mode, False, 7, 'read', priority=True)))
    return rows


def program(addressing, mode, locked, permissions, access, priority=False):
    slot = int(addressing == 'tor' or priority)
    size = 4 if addressing == 'na4' else 16
    cfg = {'tor': 8, 'na4': 16, 'napot': 24}[addressing] | permissions | (128 if locked else 0)
    config = (15 << 56) | (cfg << (8 * slot)) | (24 if priority else 0)
    lower = mode != 'M'
    denied = (not (permissions & {'read': 1, 'write': 2, 'execute': 4}[access]) and (lower or locked)) or priority
    physical = 'M' if mode.startswith('mprv') else mode
    text = HEAD + ''' csrw pmpcfg0, zero
 la t0, handler
 csrw mtvec, t0
 la t0, test_area
 srli t0, t0, 2
'''
    if addressing == 'tor':
        text += ' csrw pmpaddr0, t0\n addi t0, t0, 4\n'
    elif addressing == 'napot':
        text += ' ori t0, t0, 1\n'
    if priority:
        text += ' csrw pmpaddr0, t0\n'
    text += f''' csrw pmpaddr{slot}, t0
 mv s3, t0
 li t0, -1
 csrw pmpaddr7, t0
 li t0, {config}
 csrw pmpcfg0, t0
'''
    if locked:
        text += f''' li t0, {15 << 56}
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
    text += ' j pass\n' + TAIL + f'''.section .probe,"awx"
.balign {size}
.globl test_area
test_area:
'''
    text += ' j after_access\n .word 0\n' if access == 'execute' else ' .word 42, 0\n'
    text += ' .dword 0\n'
    return text
