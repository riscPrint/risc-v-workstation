from rvw.sim.uvm import require_evidence
import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge
from rvw.vip.ahb import Pins, CocotbAgent, RegisterScoreboard, sequences, random_sequences


@cocotb.test()
async def ram(dut):
    for name, value in vars(Pins(reset_n=0)).items():
        if name not in ('hrdata', 'hready', 'hresp'):
            getattr(dut, name).value = value
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    sc = RegisterScoreboard()
    agent = CocotbAgent(dut, sc)
    monitor = cocotb.start_soon(agent.run_monitor())
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.reset_n.value = 1
    # Interrupt a write between its accepted address and data phase.
    await FallingEdge(dut.clk)
    dut.htrans.value = 2
    dut.hwrite.value = 1
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.reset_n.value = 0
    dut.htrans.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.reset_n.value = 1
    sc.reset()
    require_evidence(agent.monitor.coverage['reset_abort'] == 1, "missing conformance evidence")
    count = 0
    try:
        for burst in [*sequences(int(os.environ.get('AHB_SEED', '1'))),
                      *random_sequences(int(os.environ.get('AHB_SEED', '1')))]:
            await agent.burst(burst)
            count += len(burst)
        await RisingEdge(dut.clk)
        if monitor.done():
            monitor.result()
        require_evidence(not os.environ.get('AHB_BUGGY'), 'corrupted DUT escaped checker')
        require_evidence(sc.count == count, "missing conformance evidence")
    finally:
        monitor.cancel()
