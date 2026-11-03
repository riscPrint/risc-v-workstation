import cocotb
from cocotb.triggers import FallingEdge, Timer
from rvw.sim.bench import start


@cocotb.test()
async def counter(dut):
    dut.io_enable.value = 0
    await start(dut)
    assert int(dut.io_count.value) == 0
    dut.io_enable.value = 1
    for expected in range(1, 261):
        await FallingEdge(dut.clk)
        await Timer(1, unit='ns')
        assert int(dut.io_count.value) == expected % 256
    dut.io_enable.value = 0
    await FallingEdge(dut.clk)
    await Timer(1, unit='ns')
    assert int(dut.io_count.value) == 4
