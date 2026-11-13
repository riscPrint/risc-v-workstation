"""Pin-level conformance; called by cocotb_smoke.py."""
import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge
from rvw.vip.apb import CocotbAgent, RegisterScoreboard, sequences, ProtocolError


@cocotb.test()
async def ram(dut):
    for name in ('reset_n', 'psel', 'penable', 'pwrite', 'paddr', 'pwdata', 'pstrb', 'pprot'):
        getattr(dut, name).value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    sc = RegisterScoreboard()
    agent = CocotbAgent(dut, sc)
    monitor = cocotb.start_soon(agent.run_monitor())
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.reset_n.value = 1
    try:
        for t in sequences(int(os.environ.get('APB_SEED', '1'))):
            await agent.transfer(t)
        await RisingEdge(dut.clk)
        if monitor.done():
            monitor.result()
        assert not os.environ.get('APB_BUGGY'), 'corrupted DUT escaped checker'
        assert sc.count == 98
    finally:
        monitor.cancel()
