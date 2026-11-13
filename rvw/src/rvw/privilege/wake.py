"""Locally enabled WFI programs using a project-owned CLINT map."""
from .programs import head, tail, xlen, interrupt_cause


def programs(config):
    timer = config['timer']
    required = {'mtime', 'mtimecmp', 'msip', 'delta'}
    if set(timer) != required or any(type(timer[k]) is not int or timer[k] < 0 for k in required):
        raise ValueError('timer needs integer mtime, mtimecmp, msip and delta')
    if not 1 <= timer['delta'] <= 1000000:
        raise ValueError('timer delta must be in 1..1000000')
    if timer['mtime'] % 8 or timer['mtimecmp'] % 8 or timer['msip'] % 4:
        raise ValueError('timer registers must be aligned')
    wide = xlen(config) == 64
    rows = []
    for source, cause in [('software', 3), ('timer', 7)]:
        for enabled in [False, True]:
            bit = 1 << cause
            store_max = ' sd t1, 0(t0)\n' if wide else ' sw t1, 4(t0)\n sw t1, 0(t0)\n'
            setup = f''' li t0, {timer['mtimecmp']}
 li t1, -1
{store_max} li t0, {timer['msip']}
 sw zero, 0(t0)
'''
            if source == 'software':
                stimulus = f"li t0, {timer['msip']}\n li t1, 1\n sw t1, 0(t0)"
            elif not wide:
                # RV32 reads mtime high/low/high and writes mtimecmp high last.
                stimulus = f'''li t0, {timer['mtime']}
read_mtime:
 lw t2, 4(t0)
 lw t1, 0(t0)
 lw t3, 4(t0)
 bne t2, t3, read_mtime
 li t4, {timer['delta']}
 add t1, t1, t4
 sltu t4, t1, t4
 add t2, t2, t4
 li t0, {timer['mtimecmp']}
 li t4, -1
 sw t4, 4(t0)
 sw t1, 0(t0)
 sw t2, 4(t0)'''
            else:
                stimulus = f'''li t0, {timer['mtime']}
 ld t1, 0(t0)
 li t2, {timer['delta']}
 add t1, t1, t2
 li t0, {timer['mtimecmp']}
 sd t1, 0(t0)'''
            # The handler checks an independent instruction interval. WFI may
            # return early; only eventual pending and completion are required.
            text = head(config) + setup + f''' la t0, handler
 csrw mtvec, t0
 li s0, 0x12345
 li t0, {bit}
 csrw mie, t0
 {stimulus}
.globl wake_start, wake_end
wake_start:
 {'csrsi mstatus, 8' if enabled else 'csrci mstatus, 8'}
 wfi
wait_pending:
 csrr t0, mip
 li t1, {bit}
 and t0, t0, t1
 beqz t0, wait_pending
 {'j wait_pending' if enabled else 'j check_state'}
wake_end:
 j fail
handler:
 csrr t0, mcause
 li t1, {interrupt_cause(config, cause)}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, wake_start
 bltu t0, t1, fail
 la t1, wake_end
 bgeu t0, t1, fail
 csrr t0, mstatus
 andi t0, t0, 8
 bnez t0, fail
 {'j check_state' if enabled else 'j fail'}
check_state:
 li t0, 0x12345
 bne s0, t0, fail
 csrw mie, zero
 csrci mstatus, 8
 {setup}
 j pass
''' + tail(config)
            rows.append(dict(id=f'wfi-{source}-mie-{int(enabled)}', family='wfi', source=source,
                enabled=enabled, bins=[f'wfi.{source}.mie.{int(enabled)}'], assembly=text))
    return rows
