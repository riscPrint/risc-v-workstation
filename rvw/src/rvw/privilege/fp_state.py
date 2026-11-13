"""Machine-mode lazy FP context slice. Requires F and Zicsr."""

def lazy_state():
    # FS initial/clean remain until an FP destination write. Trap checks use FS off.
    return '''.section .text.init
.globl _start
.option norvc
_start:
  la t0, trap
  csrw mtvec, t0
  li s0, 0
  li t0, 0x6000
  csrc mstatus, t0
  fmv.w.x f0, zero
  li t0, 1
  bne s0, t0, fail
  li t0, 0x2000
  csrs mstatus, t0
  csrr t1, mstatus
  li t2, 0x6000
  and t1, t1, t2
  bne t1, t0, fail
  li t0, 0x6000
  csrc mstatus, t0
  li t0, 0x4000
  csrs mstatus, t0
  csrr t1, mstatus
  li t2, 0x6000
  and t1, t1, t2
  bne t1, t0, fail
  fmv.w.x f0, zero
  csrr t1, mstatus
  li t0, 0x6000
  and t1, t1, t0
  bne t1, t0, fail
  li t0, 1
  j finish
trap:
  csrr t0, mcause
  li t1, 2
  bne t0, t1, fail
  addi s0, s0, 1
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  mret
fail:
  li t0, 3
finish:
  la t1, tohost
  sw t0, 0(t1)
  j finish
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
'''



def programs(config):
    base = config.get('isa', '').split('_')[0]
    if not base.startswith(('rv32', 'rv64')) or 'f' not in base[4:]:
        raise ValueError('FP context slice requires an ISA with F')
    if config.get('modes', ['M']) != ['M']:
        raise ValueError('FP context slice currently supports machine mode only')
    # The campaign linker collects .text, so do not use a separate init section.
    return [dict(id='fp-context-fs', family='fp-state',
                 bins=['fp.fs.off.trap', 'fp.fs.initial', 'fp.fs.clean.dirty'],
                 assembly=lazy_state().replace('.text.init', '.text'))]
