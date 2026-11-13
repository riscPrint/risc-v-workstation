"""Self-checking RV64 privilege programs. No core-specific addresses."""

SPEC = 'https://docs.riscv.org/reference/isa/v20260120/priv/machine.html'
LINK = '''OUTPUT_ARCH("riscv")
ENTRY(_start)
SECTIONS {
 . = 0x80000000; .text : { *(.text) }
 . = ALIGN(4096); .data : { *(.data) }
 . = ALIGN(4096); .tohost : { *(.tohost) }
}
'''
TAIL = '''fail:
 li t1, 3
 j finish
pass:
 li t1, 1
finish:
 li t0, 0x20000
 csrc mstatus, t0
 la t0, tohost
 sd t1, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
'''
HEAD = '''.option norvc
.section .text
.globl _start
_start:
 la t0, fail
 csrw mtvec, t0
 csrw mie, zero
 csrw medeleg, zero
 csrw mideleg, zero
 li t0, -1
 csrw pmpaddr0, t0
 li t0, 15
 csrw pmpcfg0, t0
 csrw satp, zero
 li t0, 0x7e190a
 csrc mstatus, t0
'''


# Machine-only preamble. A core without S-mode or PMP has no satp, medeleg,
# mideleg or pmp CSRs, and the full HEAD traps on them.
M_HEAD = '''.option norvc
.section .text
.globl _start
_start:
 la t0, fail
 csrw mtvec, t0
 csrw mie, zero
 li t0, 0x7e190a
 csrc mstatus, t0
'''
TAIL32 = TAIL.replace(' sd t1, 0(t0)', ' sw t1, 0(t0)\n sw zero, 4(t0)')


def xlen(config):
    """XLEN from the campaign isa. The default stays RV64."""
    return 32 if config.get('isa', 'rv64').startswith('rv32') else 64


def head(config):
    priv = config.get('priv', 'msu')
    if priv == 'm':
        return M_HEAD
    if priv == 'mu':
        # M and U only: no satp or delegation CSRs.
        return HEAD.replace(' csrw medeleg, zero\n', '').replace(' csrw mideleg, zero\n', '').replace(' csrw satp, zero\n', '')
    return HEAD


def tail(config):
    return TAIL32 if xlen(config) == 32 else TAIL


def interrupt_cause(config, cause):
    """mcause value of an interrupt: the top XLEN bit plus the code."""
    return (1 << (xlen(config) - 1)) | cause


def controls(config):
    """Cross TVM/TW/TSR with real M/S/U entry and both bit states.

    M traps are used to check lower-mode exits. The second entry clears the
    control bit and proves that the first trap did not prevent later use.
    """
    rows = []
    for mode in config.get('modes', ['M', 'S', 'U']):
        for control, instructions in {'tvm': ['satp-read', 'satp-write', 'sfence'],
                                      'tw': ['wfi'], 'tsr': ['sret']}.items():
            for enabled in (False, True):
                for instruction in instructions:
                    ident = f'{control}-{mode.lower()}-{int(enabled)}-{instruction}'
                    rows.append(dict(id=ident, family='supervisor', control=control,
                        mode=mode, enabled=enabled, instruction=instruction,
                        bins=[f'control.{control}.{mode}.{int(enabled)}', f'instruction.{instruction}'],
                        assembly=control_program(control, instruction, mode, enabled)))
    return rows


def control_program(control, instruction, mode, enabled):
    bit = {'tvm': 20, 'tw': 21, 'tsr': 22}[control]
    op = {'satp-read': 'csrr a0, satp', 'satp-write': 'csrw satp, zero',
          'sfence': 'sfence.vma x0, x0', 'wfi': 'wfi', 'sret': 'sret'}[instruction]
    denied = mode == 'U' or (mode == 'S' and enabled)
    # SRET in M returns to S. SRET in S also returns to S (SPP=1).
    exit_mode = 'S' if instruction == 'sret' and not denied else mode
    wake = 'li t0, 2\n csrw mie, t0\n csrw mideleg, t0\n csrs mip, t0'
    code = HEAD + f''' la t0, trap
 csrw mtvec, t0
 li s0, 0
 li s1, {int(enabled) << bit}
 csrs mstatus, s1
 # SSIP is locally enabled and pending, so WFI need not wait for a timer.
 {wake if instruction == 'wfi' and mode != 'U' else ''}
 la t0, done
 csrw sepc, t0
 li t0, 256
 csrs mstatus, t0
'''
    if mode == 'M':
        code += ' j access_site\n'
    else:
        code += f''' li t0, {int(mode == 'S') << 11}
 csrs mstatus, t0
 la t0, access_site
 csrw mepc, t0
 mret
'''
    code += f'''access_site:
 {op}
 {'j fail' if instruction == 'sret' else 'nop'}
done:
 ecall
 j fail
trap:
 csrr t0, mcause
 li t1, {2 if denied else {'M': 11, 'S': 9, 'U': 8}[exit_mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'access_site' if denied else 'done'}
 bne t0, t1, fail
 # Control bits survive the trap. Clear them, then retry in S-mode.
 csrr t0, mstatus
 and t0, t0, s1
 bne t0, s1, fail
 bnez s0, pass
 li s0, 1
 li t0, {1 << bit}
 csrc mstatus, t0
 li s1, 0
 {wake if instruction == 'wfi' else ''}
 la t0, retry_trap
 csrw mtvec, t0
 li t0, 0x1800
 csrc mstatus, t0
 li t0, 0x900
 csrs mstatus, t0
 la t0, retry_done
 csrw sepc, t0
 la t0, retry
 csrw mepc, t0
 mret
retry:
 {op}
 {'j fail' if instruction == 'sret' else 'nop'}
retry_done:
 ecall
 j fail
retry_trap:
 csrr t0, mcause
 li t1, 9
 bne t0, t1, fail
 csrr t0, mepc
 la t1, retry_done
 bne t0, t1, fail
 j pass
'''
    return code + TAIL
