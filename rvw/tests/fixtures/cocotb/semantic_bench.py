import os
import json
import cocotb
from cocotb.triggers import Timer, RisingEdge, ReadOnly, FallingEdge
from rvw.sim.bench import start


@cocotb.test()
async def scheduling_and_timer(dut):
    dut.enable.value = 0
    await start(dut)
    assert int(dut.count.value) == 0
    dut.enable.value = 1
    for count in range(1, 4):
        await RisingEdge(dut.clk)
        # Verilator settles in its edge callback. Use a timed observation
        # common to both adapter profiles.
        await Timer(1, unit='ns')
        assert int(dut.count.value) == count


@cocotb.test()
async def value_semantics(dut):
    dut.enable.value = 0
    await start(dut)
    await Timer(1, unit='ns')
    if json.loads(os.environ['RVW_COCOTB_BINDINGS'])['backend'] == 'icarus':
        await ReadOnly()
        assert str(dut.unknown_value.value).lower() == 'x'
        assert str(dut.high_z.value).lower() == 'z'
    else:
        assert dut.unknown_value.value.is_resolvable
        assert dut.high_z.value.is_resolvable
