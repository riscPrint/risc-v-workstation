"""Two-hart mailbox shootdown. No platform-specific interrupt controller."""


def assembly(s):
    from .mmu import DATA, ROOT, FLAGS
    from .mmu_paging import geometry, page_tables
    g = geometry(s)
    flags = sum(FLAGS[f] for f in s['flags'])
    tables, leaf = page_tables(s, ROOT, DATA, flags)
    replacement = ((DATA + 4096) >> 12 << 10) | flags
    ipi = s.get('ipi')
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
 li t0, {g.satp(ROOT, s.get('asid', 0))}
 csrw satp, t0
 sfence.vma x0, x0
 li t0, 0xe1800
 csrc mstatus, t0
 li s0, 0x40000000
 li s1, {DATA + 8192}
 csrr s2, mhartid
 li t0, 1
 beq s2, t0, remote
 bnez s2, park
local:
 ld t0, 0(s1)
 beqz t0, local
 fence r, rw
 li t0, {leaf}
 li t1, {replacement}
 sd t1, 0(t0)
 fence rw, w
 li t0, 1
 sd t0, 8(s1)
wait_ack:
 ld t0, 16(s1)
 beqz t0, wait_ack
 fence r, rw
 li t0, 1
 sd t0, 24(s1)
 j park
remote:
 li t0, 0x20800
 csrs mstatus, t0
 ld a0, 0(s0)
 li t0, 0x20000
 csrc mstatus, t0
 li t0, 42
 bne a0, t0, fail
 fence rw, w
 li t0, 1
 sd t0, 0(s1)
wait_request:
 ld t0, 8(s1)
 beqz t0, wait_request
 fence r, rw
 sfence.vma x0, x0
 fence rw, w
 li t0, 1
 sd t0, 16(s1)
wait_complete:
 ld t0, 24(s1)
 beqz t0, wait_complete
 fence r, rw
 li t0, 0x20800
 csrs mstatus, t0
 ld a0, 0(s0)
 li t0, 0x20000
 csrc mstatus, t0
 li t0, 43
 bne a0, t0, fail
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
    if ipi:
        from .mmu import number
        remote_msip = number(ipi['msip']) + number(ipi['stride'])
        code = code.replace(' la t0, fail', ' la t0, ipi_handler', 1)
        code = code.replace(' sd t0, 8(s1)\nwait_ack:', f' sd t0, 8(s1)\n li t5, {remote_msip}\n sw t0, 0(t5)\nwait_ack:')
        code = code.replace('remote:\n', 'remote:\n li s3, 0\n li t0, 8\n csrs mie, t0\n csrs mstatus, t0\n')
        code = code.replace(' ld t0, 8(s1)\n beqz t0, wait_request', ' beqz s3, wait_request')
        code = code.replace('fail:\n', f'''ipi_handler:
 csrr t5, mcause
 li t6, 0x8000000000000003
 bne t5, t6, fail
 li t5, {remote_msip}
 sw zero, 0(t5)
 li s3, 1
 mret
fail:
''')
    return code + '.section .data\n .dword 42\n .zero 4088\n .dword 43\n .zero 4088\n .zero 32\n'


def validate(s):
    if s.keys() - {'id', 'mode', 'level', 'flags', 'access', 'expect', 'bins', 'shootdown', 'asid', 'ipi'}:
        raise ValueError('unsupported shootdown option')
    if s.get('shootdown') is not True or s.get('mode') not in ('sv39', 'sv48', 'sv57') or s['access'] != 'load' or s['level'] != 0 or s['expect'] != 'success' or not set('VRAD') <= set(s['flags']):
        raise ValueError('shootdown requires a successful RV64 level-zero readable mapping with A/D')

    if 'ipi' in s:
        from .mmu import number
        ipi = s['ipi']
        if not isinstance(ipi, dict) or set(ipi) != {'msip', 'stride'} or number(ipi['msip']) < 0 or number(ipi['msip']) % 4 or number(ipi['stride']) < 4 or number(ipi['stride']) % 4:
            raise ValueError('ipi requires aligned project msip and stride')
