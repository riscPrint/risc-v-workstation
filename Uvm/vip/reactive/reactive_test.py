import os
import importlib
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge,ClockCycles,Timer


@cocotb.test()
async def read_response(dut):
    protocol=os.environ['VIP_PROTOCOL'];seed=int(os.environ['VIP_SEED']);bad=bool(int(os.environ['VIP_BAD']))
    agent=importlib.import_module('rvw.vip.'+protocol).CocotbAgent(dut)
    dut.reset_n.value=0;dut.go.value=0;dut.request_address.value=random.Random(seed).randrange(4)*4
    for name in (('pready','prdata','pslverr') if protocol=='apb' else ('hready','hrdata','hresp')):
        getattr(dut,name).value=int(name in ('pready','hready'))
    cocotb.start_soon(Clock(dut.clk,10,unit='ns').start())
    task=cocotb.start_soon(agent.run_subordinate(seed,bad))
    try:
        await ClockCycles(dut.clk,3);await FallingEdge(dut.clk);dut.reset_n.value=1;dut.go.value=1
        for _ in range(100):
            await ClockCycles(dut.clk,1);await Timer(1,unit='ns')
            if task.done():task.result()
            if int(dut.done.value):break
        else:raise AssertionError('reactive DUT manager timeout')
        assert int(dut.result.value)==0,protocol.upper()+'_REACTIVE_DATA'
    finally:task.cancel()
