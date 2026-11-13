import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge,ClockCycles


@cocotb.test()
async def read_words(dut):
    proto=os.environ['VIP_PROTOCOL'];rng=random.Random(17)
    dut.reset_n.value=0;dut.buggy.value=int(os.environ['VIP_BAD']);dut.salt.value=0x1937ABCD
    if proto in ('axi','axilite'):
        from rvw.vip.axi import CocotbAgent,Address,Pins
        agent=CocotbAgent(dut,'axi',lite=proto=='axilite');agent.drive(Pins())
    else:
        from rvw.vip.tilelink import CocotbAgent,Request,Pins
        agent=CocotbAgent(dut,'tl');agent.drive(Pins())
    cocotb.start_soon(Clock(dut.clk,10,unit='ns').start())
    await ClockCycles(dut.clk,3);await FallingEdge(dut.clk);dut.reset_n.value=1
    for i in range(4):
        address=rng.randrange(256)*4
        if proto in ('axi','axilite'): response=await agent.transfer(Address(address,id=0 if proto=='axilite' else i))
        else: response=await agent.transfer([Request(address=address,source=i)])
        assert len(response)==1 and response[0].data==address^0x1937ABCD,proto.upper()+'_RTL_DATA'
