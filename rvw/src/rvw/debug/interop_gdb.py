"""GDB Python script for `rvw debug interop`. Runs inside GDB (-batch -x). Prints RVW_* markers."""
import os

import gdb  # pylint: disable=import-error

MASK = (1 << 64) - 1


def mark(name, ok, detail=''):
    print(('RVW_CHECK:' if ok else 'RVW_FAILURE:') + name + ('' if ok else ':' + detail), flush=True)


def val(expr):
    return int(gdb.parse_and_eval(expr)) & MASK


def counter():
    return val('*(unsigned int *)&counter')


def run(command):
    return gdb.execute(command, to_string=True)


def fresh():
    run('maintenance flush register-cache')
    run('maint flush dcache')


def attempt(command):
    try:
        run(command)
        return None
    except gdb.error as exc:
        return str(exc).replace('\n', ' ')


def main():
    print('RVW_GDB_VERSION:' + gdb.VERSION, flush=True)
    for command in ('set pagination off', 'set confirm off', 'set remotetimeout 30', 'set width 0'):
        run(command)
    run('file ' + os.environ['RVW_ELF'])
    run('target extended-remote | ' + os.environ['RVW_OPENOCD_PIPE'])
    print('RVW_CONNECTED', flush=True)
    run('load')
    fresh()
    first = int.from_bytes(bytes.fromhex(os.environ['RVW_FIRST_WORD']), 'little')
    mark('load', val('*(unsigned int *)&_start') == first, 'first word differs after load')
    run('set $pc = _start')
    # A value that uses every bit an RV32 register has, and more on RV64.
    value = 0x123456789 if gdb.parse_and_eval('$s1').type.sizeof == 8 else 0x12345678
    run(f'set $s1 = {value:#x}')
    fresh()
    mark('register_write', val('$s1') == value and val('$pc') == val('&_start'), 'readback differs')
    run('set var *(unsigned int *)&counter = 5')
    fresh()
    mark('memory_write', counter() == 5, 'counter readback differs')
    # An instruction address avoids GDB function-prologue skipping.
    run('break *target')
    run('continue')
    fresh()
    mark('breakpoint', val('$pc') == val('&target') and counter() == 6,
         f'pc 0x{val("$pc"):x} counter %d' % counter())
    run('delete')
    run('set $pc = loop')
    before = counter()
    error = attempt('hbreak *target') or attempt('continue')
    fresh()
    mark('hardware_breakpoint', not error and val('$pc') == val('&target') and counter() == before + 1,
         error or f'pc 0x{val("$pc"):x} counter %d' % counter())
    run('delete')
    run('set $pc = target')
    fresh()
    s1 = val('$s1')
    run('stepi')
    fresh()
    mark('stepi', val('$pc') == val('&target') + 4 and val('$s1') == (s1 + 1) & MASK,
         f'pc 0x{val("$pc"):x}')
    run('stepi')
    fresh()
    mark('stepi_jump', val('$pc') == val('&loop'), f'pc 0x{val("$pc"):x}')
    if os.environ.get('RVW_WATCHPOINT') == '0':
        print('RVW_UNSUPPORTED:watchpoint:profile declares no store triggers', flush=True)
    else:
        run('set $pc = loop')
        before = counter()
        error = attempt('watch *(unsigned int *)&counter') or attempt('continue')
        fresh()
        mark('watchpoint', not error and counter() == before + 1 and val('&loop') < val('$pc') <= val('&target'),
             error or f'pc 0x{val("$pc"):x} counter %d' % counter())
        run('delete')
    reset_pc = os.environ.get('RVW_RESET_PC')
    if reset_pc:
        run('monitor reset halt')
        fresh()
        mark('reset_halt', val('$pc') == int(reset_pc, 0), f'pc 0x{val("$pc"):x}')
    print('RVW_COMPLETE', flush=True)
    run('detach')


try:
    main()
except gdb.error as exc:
    print('RVW_FAILURE:gdb:' + str(exc).replace('\n', ' '), flush=True)
