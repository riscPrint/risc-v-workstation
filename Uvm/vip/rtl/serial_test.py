"""Real RTL tests with seeded stimulus and independent expected values."""
from rvw.sim.uvm import require_evidence
import os
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge,RisingEdge,ClockCycles,Timer


@cocotb.test()
async def serial(dut):
    proto=os.environ['VIP_PROTOCOL']; seed=int(os.environ.get('VIP_SEED','1'))
    rng=random.Random(seed)
    for name,value in dict(reset_n=0,buggy=int(os.environ['VIP_BAD']),spi_cs_n=1,
        spi_sclk=0,spi_mosi=0,rx=1,i2c_scl_low=0,i2c_sda_low=0,
        gpio_external=0,gpio_direction=0,gpio_output=0).items(): getattr(dut,name).value=value
    cocotb.start_soon(Clock(dut.clk,10,unit='ns').start())
    await ClockCycles(dut.clk,3); await FallingEdge(dut.clk); dut.reset_n.value=1
    if proto=='spi':
        from rvw.vip.spi import CocotbAgent
        agent=CocotbAgent(dut,'spi')
        for _ in range(4):
            data=rng.randrange(256)
            require_evidence(await agent.transfer(data)==data, 'SPI_RTL_DATA')
    elif proto=='uart':
        from rvw.vip.uart import CocotbAgent,Frame
        seen=[];agent=CocotbAgent(dut,hook=seen.append)
        task=cocotb.start_soon(agent.run_monitor())
        values=[rng.randrange(256) for _ in range(4)]
        try:
            for data in values: await agent.send(Frame(data))
            await ClockCycles(dut.clk,10)
            require_evidence(seen==[Frame(data) for data in values], 'UART_RTL_DATA')
        finally: task.cancel()
    elif proto=='gpio':
        from rvw.vip.gpio import CocotbAgent,Config,sequences
        agent=CocotbAgent(dut,'gpio',Config(rising=1,falling=2,high=4,low=8))
        # Reset the reference and DUT together before the first sample.
        for p in sequences(seed,8): await agent.drive(p)
    elif proto=='i2c':
        from rvw.vip.i2c import CocotbAgent
        agent=CocotbAgent(dut,'i2c',resolved_open_drain=True)
        require_evidence(await agent.transfer(0x35,[rng.randrange(256)])==[True,True], 'I2C_RTL_ACK')
