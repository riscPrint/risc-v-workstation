"""Two-hart software RSW update versus hardware A/D update campaign."""


def assembly(s):
    from .mmu import ROOT, DATA
    from .mmu_paging import geometry, page_tables
    g = geometry(s)
    tables, leaf = page_tables(s, ROOT, DATA, 7)
    expected = (DATA >> 12 << 10) | 0x1c7
    code = f'''.option norvc
.section .text
.globl _start
_start:
 la t0, fail
 csrw mtvec, t0
 csrw mie, zero
 li t0, -1
 csrw pmpaddr0, t0
 li t0, 15
 csrw pmpcfg0, t0
 li t0, 0x2000000000000000
 csrs menvcfg, t0
 li t0, {g.satp(ROOT)}
 csrw satp, t0
 sfence.vma x0, x0
 li s0, {leaf}
 li s1, {DATA + 8192}
 csrr s2, mhartid
 li t0, 1
 beq s2, t0, remote
 bnez s2, park
wait_ready:
 ld t0, 0(s1)
 beqz t0, wait_ready
 fence r, rw
 li t0, 1
 sd t0, 8(s1)
 li t0, 256
 amoor.d.aqrl zero, t0, (s0)
wait_done:
 ld t0, 16(s1)
 beqz t0, wait_done
 fence r, rw
 ld t0, 0(s0)
 li t1, {expected}
 bne t0, t1, fail
 li t0, {DATA}
 ld t0, 0(t0)
 li t1, 43
 bne t0, t1, fail
 li t1, 1
 j finish
remote:
 li t0, 1
 fence rw, w
 sd t0, 0(s1)
wait_start:
 ld t0, 8(s1)
 beqz t0, wait_start
 fence r, rw
 li t3, 0x40000000
 li t0, 0x20800
 csrs mstatus, t0
 li a0, 43
 sd a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 fence rw, w
 li t0, 1
 sd t0, 16(s1)
 j park
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
    return code + '.section .data\n .dword 42\n .zero 8184\n .zero 24\n'


def validate(s):
    if s.keys() - {'id', 'mode', 'level', 'flags', 'access', 'expect', 'bins', 'atomic_ad'}:
        raise ValueError('unsupported atomic_ad option')
    if s.get('atomic_ad') is not True or s.get('mode') not in ('sv39', 'sv48', 'sv57') or s['level'] != 0 or s['flags'] != 'VRW' or s['access'] != 'store' or s['expect'] != 'success':
        raise ValueError('atomic_ad requires RV64 level-zero VRW store with hardware A/D')
