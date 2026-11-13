"""Small core-independent RV64H delegation programs with literal expectations."""


def cases():
    result = []
    for mode, delegate in [('vs', False), ('vu', False), ('vu', True)]:
        mpp = 0x800 if mode == 'vs' else 0
        source = f'''.section .text
.globl _start
_start:
  li t0, -1
  csrw pmpaddr0, t0
  li t0, 15
  csrw pmpcfg0, t0
  la t0, host
  csrw stvec, t0
  la t0, supervisor
  csrw vstvec, t0
  li t0, 0x500
  csrw medeleg, t0
  li t0, {0x100 if delegate else 0}
  csrw hedeleg, t0
  li t0, {mpp}
  csrw mstatus, t0
  li t0, 0x80
  slli t0, t0, 32
  csrs mstatus, t0
  la t0, guest
  csrw mepc, t0
  mret
guest:
  ecall
supervisor:
  ecall
host:
  wfi
'''
        expected = ([dict(mode=0, cause=8, virtual_after=True, mode_after=1),
                     dict(mode=1, cause=10, virtual_after=False, mode_after=1)]
                    if delegate else [dict(mode=1 if mode == 'vs' else 0,
                                           cause=10 if mode == 'vs' else 8,
                                           virtual_after=False, mode_after=1)])
        result.append(dict(name=f'{mode}-ecall-to-' + ('vs-hs' if delegate else 'hs'),
                           source=source, expected=expected))
    return result
