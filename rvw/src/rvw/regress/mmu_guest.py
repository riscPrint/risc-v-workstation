"""Bounded HLV data-access tests with independent VS and G page tables."""


def assembly(s):
    if 'guest_mode' in s or 'guest_op' in s or 'ad_expect' in s or s.get('mode') != 'sv39':
        from .mmu_hypervisor import assembly as extended_assembly
        return extended_assembly(s)
    from .mmu import ROOT, DATA, FLAGS
    from .mmu_paging import MODES, page_tables
    g = MODES['sv39']
    flags = sum(FLAGS[f] for f in set(s['flags']))
    tables, _ = page_tables(s, ROOT, DATA, flags)
    guest_root = 0x80020000  # Sv39x4 root requires 16 KiB alignment.
    gflags = sum(FLAGS[f] for f in set(s.get('guest_flags', 'VRWXUAD')))
    gt = [0] * 2048
    # Both VS page-table GPAs and payload GPA fall in this 1 GiB leaf.
    gt[2] = ((guest_root + 16384) >> 12 << 10) | 1
    middle = [0] * 512
    middle[0] = (0x80000000 >> 12 << 10) | 0xdf
    middle[1] = (DATA >> 12 << 10) | gflags
    fault = s['expect'] != 'success'
    cause = 21 if s.get('guest_fault') else 13
    code = f'''.option norvc
.section .text
.globl _start
_start:
 csrr t0, mhartid
 bnez t0, park
 la t0, trap
 csrw mtvec, t0
 csrw mie, zero
 csrw medeleg, zero
 csrw mideleg, zero
 li t0, -1
 csrw pmpaddr0, t0
 li t0, 15
 csrw pmpcfg0, t0
 li t0, 256
 csrw hstatus, t0
 li t0, {g.satp(ROOT)}
 csrw vsatp, t0
 li t0, {(8 << 60) | (s.get('vmid', 0) << 44) | (guest_root >> 12)}
 csrw hgatp, t0
 csrr t1, hgatp
 bne t0, t1, fail
 hfence.gvma x0, x0
 hfence.vvma x0, x0
 li t3, 0x40000000
access_site:
 hlv.d a0, (t3)
 {'j fail' if fault else 'li t1, 42'}
 bne a0, t1, fail
 j pass
trap:
 {'csrr t0, mcause' if fault else 'j fail'}
 li t1, {cause}
 bne t0, t1, fail
 csrr t0, mtval
 li t1, 0x40000000
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
'''
    if s.get('guest_fault'):
        code += f''' csrr t0, mtval2
 li t1, {DATA >> 2}
 bne t0, t1, fail
'''
    code += '''pass:
 li t1, 1
 j finish
fail:
 li t1, 3
finish:
 la t0, tohost
 sd t1, 0(t0)
park:
 j park
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
.section .tables,"aw"
'''
    for table in tables:
        code += '\n'.join(f' .dword {v}' for v in table) + '\n'
    code += f' .zero {guest_root - ROOT - len(tables) * 4096}\n'
    code += '\n'.join(f' .dword {v}' for v in gt) + '\n'
    code += '\n'.join(f' .dword {v}' for v in middle) + '\n'
    code += '.section .data\n .dword 42\n'
    return code


def validate(s):
    from .mmu import FLAGS
    if s.get('mode') not in ('sv39', 'sv48', 'sv57') or s['level'] != 0 or s['access'] not in ('load', 'store') or s['expect'] not in ('success', 'page-fault', 'virtual-instruction'):
        raise ValueError('guest requires Sv39 level-zero load with success or page-fault')
    if not isinstance(s.get('guest'), bool) or s['guest'] is not True:
        raise ValueError('guest must be true')
    if not isinstance(s.get('guest_flags', ''), str) or set(s.get('guest_flags', '')) - FLAGS.keys():
        raise ValueError('invalid G-stage flags')
    if type(s.get('guest_fault', False)) is not bool or type(s.get('vmid', 0)) is not int or not 0 <= s.get('vmid', 0) < 16384:
        raise ValueError('invalid guest fault or VMID')
    if s.keys() - {'id', 'mode', 'level', 'flags', 'access', 'expect', 'bins', 'guest', 'guest_flags', 'guest_fault', 'vmid', 'guest_mode', 'guest_op', 'ad_mode', 'ad_expect', 'guest_trap', 'guest_switch'}:
        raise ValueError('unsupported guest scenario option')

    if s.get('guest_mode', 'sv39') not in ('sv39', 'sv48', 'sv57') or s.get('guest_op', 'hlv.d') not in ('hlv.d', 'hlvx.wu', 'hsv.d', 'vs-satp', 'vs-sfence', 'vs-sret'):
        raise ValueError('unsupported guest mode or operation')
    if (s.get('guest_op') == 'hsv.d') != (s['access'] == 'store'):
        raise ValueError('guest operation differs from access')

    if s.get('guest_op', '').startswith('vs-') and s['expect'] != 'virtual-instruction':
        raise ValueError('VS control operations require virtual-instruction')

    if s.get('guest_trap', 'm') not in ('m', 'hs'):
        raise ValueError('guest_trap must be m or hs')
    if 'guest_switch' in s and type(s['guest_switch']) is not bool:
        raise ValueError('guest_switch must be boolean')
    if s.get('guest_switch') and (s.get('guest_op', 'hlv.d') != 'hlv.d' or s['expect'] != 'success' or s.get('guest_trap', 'm') != 'm'):
        raise ValueError('guest_switch requires a successful M-mode HLV.D')
