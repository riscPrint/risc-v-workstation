from rvw.sim.uvm import require_evidence
import os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge
from rvw.vip.axis import Beat, CocotbAgent, Scoreboard, sequences


@cocotb.test()
async def fifo(dut):
    dut.reset_n.value = 0
    dut.s_tvalid.value = 0
    dut.m_tready.value = 0
    for name in ('tdata', 'tkeep', 'tstrb', 'tlast', 'tid', 'tdest', 'tuser'):
        getattr(dut, 's_' + name).value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    sc = Scoreboard()
    tx = CocotbAgent(dut, 's', sc.expect)
    rx = CocotbAgent(dut, 'm', sc.observe)
    mt = cocotb.start_soon(tx.run_monitor())
    mr = cocotb.start_soon(rx.run_monitor())
    sink = cocotb.start_soon(rx.run_subordinate(int(os.environ.get('AXIS_SEED', '1'))))
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.reset_n.value = 1
    try:
        for beat in sequences(int(os.environ.get('AXIS_SEED', '1'))):
            await tx.send(beat)
        for _ in range(100):
            await RisingEdge(dut.clk)
        if mt.done(): mt.result()
        if mr.done(): mr.result()
        require_evidence(not os.environ.get('AXIS_BUGGY'), 'corruption escaped checker')
        tx.monitor.finish(); rx.monitor.finish(); sc.finish()
        require_evidence(sc.count == 66, "missing conformance evidence")
        require_evidence(rx.monitor.coverage['stall'], "missing conformance evidence")
    finally:
        mt.cancel(); mr.cancel(); sink.cancel()
