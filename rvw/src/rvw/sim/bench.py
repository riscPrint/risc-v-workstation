"""Optional project-bound cocotb clock/reset setup."""
import json
import os


async def start(dut):
    """Start the configured clock, assert reset, then release on a falling edge.

    Call once per test, before driving functional stimulus. Cocotb owns clock
    task cleanup. Signal names come only from the project manifest.
    """
    import cocotb
    from cocotb.clock import Clock
    from cocotb.triggers import FallingEdge, Timer
    request = json.loads(os.environ['RVW_COCOTB_BINDINGS'])
    if 'clock' not in request:
        return
    spec = request['clock']
    clock = getattr(dut, spec['signal'])
    reset = request.get('reset')
    if reset:
        getattr(dut, reset['signal']).value = reset['active']
    cocotb.start_soon(Clock(clock, spec['period_ns'], unit='ns').start())
    if reset:
        for _ in range(reset['cycles']):
            await FallingEdge(clock)
        getattr(dut, reset['signal']).value = 1 - reset['active']
        await Timer(spec['period_ns'] / 4, unit='ns')
