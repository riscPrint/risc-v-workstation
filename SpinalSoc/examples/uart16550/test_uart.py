"""Directed 16550 register and serial tests with the independent UART VIP."""
import json
from pathlib import Path
from types import SimpleNamespace
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge, ClockCycles
from rvw.sim.bench import start
from rvw.vip.uart import CocotbAgent, Config, Frame, Scoreboard


@cocotb.test()
async def directed(dut):
    if dut._name == 'Uart16550Full':
        pins = {name:getattr(dut,'io_bus_'+name) for name in
                ('PADDR','PSEL','PENABLE','PWRITE','PWDATA','PRDATA','PREADY','PSLVERROR')}
        pins.update({name:getattr(dut,'io_modem_'+name) for name in
                     ('cts_n','dsr_n','ri_n','dcd_n','rts_n','dtr_n','out1_n','out2_n')})
        pins.update(clk=dut.clk,reset=dut.reset,rxd=dut.io_serial_rxd,txd=dut.io_serial_txd,irq=dut.io_irq,rx_ready_n=dut.io_rx_ready_n,tx_ready_n=dut.io_tx_ready_n)
        d=SimpleNamespace(**pins)
    else:
        d=dut
    checks = 0
    def check(condition,message):
        nonlocal checks
        assert condition,message
        checks += 1
    async def bus(offset,data=None):
        await FallingEdge(d.clk)
        d.PADDR.value=offset;d.PWRITE.value=int(data is not None)
        d.PWDATA.value=0 if data is None else data
        d.PSEL.value=1;d.PENABLE.value=0
        await FallingEdge(d.clk)
        d.PENABLE.value=1
        await RisingEdge(d.clk)
        check(int(d.PREADY.value)==1 and int(d.PSLVERROR.value)==0,'APB completion')
        value=int(d.PRDATA.value)
        await FallingEdge(d.clk)
        d.PSEL.value=0;d.PENABLE.value=0
        return value
    class Reset:
        @property
        def value(self): return 1-int(d.reset.value)
    d.PSEL.value=0;d.PENABLE.value=0;d.PWRITE.value=0;d.PADDR.value=0;d.PWDATA.value=0
    d.rxd.value=1
    for name in ('cts_n','dsr_n','ri_n','dcd_n'):getattr(d,name).value=1
    await start(d)
    await ClockCycles(d.clk,5)
    check(await bus(12)==0,'LCR reset')
    check(await bus(16)==0,'MCR reset')
    check(await bus(20)==0x60,'THRE and TEMT reset')
    await bus(12,0x83);await bus(0,3);await bus(4,0)
    check(await bus(0)==3 and await bus(4)==0,'Divisor latch alias')
    await bus(12,3);await bus(28,0xa5)
    check(await bus(28)==0xa5,'Scratch readback')
    cfg=Config(cycles_per_bit=48)
    scoreboard=Scoreboard()
    view=SimpleNamespace(clk=d.clk,reset_n=Reset(),txd=d.txd,rxd=d.rxd)
    agent=CocotbAgent(view,tx='txd',rx='rxd',config=cfg,hook=scoreboard.observe)
    monitor=cocotb.start_soon(agent.run_monitor())
    await bus(8,15)
    for value in range(17):
        scoreboard.expect(Frame(value+0x40));await bus(0,value+0x40)
    check((await bus(20)&0x60)==0,'TX FIFO has queued data')
    check(int(d.tx_ready_n.value)==1,'DMA mode one deasserts at TX FIFO full')
    await ClockCycles(d.clk,18*11*cfg.cycles_per_bit)
    check(scoreboard.count==17,'TX FIFO drains in order through UART VIP')
    check((await bus(20)&0x60)==0x60,'TEMT includes the serial shifter')
    check(int(d.tx_ready_n.value)==0,'DMA mode one requests TX refill after empty')
    await bus(8,0x4f);await bus(4,1)
    for value in range(3):await agent.send(Frame(0x20+value))
    check((await bus(8)&15)==1,'RX trigger below four bytes')
    await agent.send(Frame(0x23))
    check((await bus(8)&0xcf)==0xc4,'RX threshold IRQ')
    check(int(d.rx_ready_n.value)==0,'DMA RX request at threshold')
    for value in range(4):
        check(await bus(0)==0x20+value,'RX FIFO order')
        check(int(d.rx_ready_n.value)==int(value==3),'DMA RX request holds until empty')
    check(not int(d.irq.value),'RX interrupt clears below threshold')
    await agent.send(Frame(0x55))
    await ClockCycles(d.clk,41*cfg.cycles_per_bit)
    check((await bus(8)&0xcf)==0xcc,'Four-character RX timeout IRQ')
    check(await bus(0)==0x55,'Timeout data read')
    await bus(4,0);await bus(8,7)
    for value in range(17):await agent.send(Frame(value))
    check(bool(await bus(20)&2),'RX overrun at sixteen bytes')
    check(not (await bus(20)&2),'LSR read clears overrun')
    for value in range(16):check(await bus(0)==value,'Overrun retains oldest FIFO data')
    check(not (await bus(20)&1),'RX FIFO empty')
    monitor.cancel()
    await bus(8,7);await bus(12,0x1b);await bus(4,4)
    parity_agent=CocotbAgent(view,tx='txd',rx='rxd',config=Config(cycles_per_bit=48,parity='even'))
    await parity_agent.send(Frame(0x55,parity_error=True))
    check((await bus(8)&15)==6,'Line-status IRQ has priority')
    check(bool(await bus(20)&4),'Parity error')
    check(not (await bus(20)&4),'LSR read clears parity error')
    check(await bus(0)==0x55,'Parity error retains received data')
    await bus(12,3)
    await agent.send(Frame(0x13,framing_error=True))
    check(bool(await bus(20)&8),'Framing error')
    await bus(0)
    d.rxd.value=0
    await ClockCycles(d.clk,12*cfg.cycles_per_bit)
    check(bool(await bus(20)&16),'Break detection')
    d.rxd.value=1
    await ClockCycles(d.clk,2*cfg.cycles_per_bit)
    await bus(8,7);await bus(4,8);await bus(16,3)
    check(int(d.rts_n.value)==0 and int(d.dtr_n.value)==0,'Modem outputs')
    d.cts_n.value=0;d.dsr_n.value=0;d.dcd_n.value=0
    await ClockCycles(d.clk,8)
    check((await bus(8)&15)==0,'Modem delta IRQ')
    check((await bus(24)&0xbb)==0xbb,'CTS DSR DCD status and delta')
    check((await bus(24)&15)==0,'MSR read clears delta bits')
    d.ri_n.value=0;await ClockCycles(d.clk,8)
    check((await bus(24)&0x44)==0x40,'RI rising edge has no trailing delta')
    d.ri_n.value=1;await ClockCycles(d.clk,8)
    check(bool(await bus(24)&4),'RI trailing edge delta')
    await bus(4,0);await bus(16,0x1f)
    await ClockCycles(d.clk,8)
    check((await bus(24)&0xf0)==0xf0,'Internal modem loopback')
    check(all(int(getattr(d,n).value) for n in ('rts_n','dtr_n','out1_n','out2_n')),'Loopback holds modem outputs inactive')
    await bus(0,0xa5)
    await ClockCycles(d.clk,12*cfg.cycles_per_bit)
    check(int(d.txd.value)==1,'Loopback holds external TX idle')
    check(await bus(0)==0xa5,'Serial loopback data')
    await bus(16,0);await bus(8,0)
    await agent.send(Frame(0x42));await agent.send(Frame(0x43))
    check((await bus(8)&0xc0)==0,'FIFO disable IIR bits')
    check(bool(await bus(20)&2),'One-byte mode overrun')
    check(await bus(0)==0x42,'One-byte mode retains holding byte')
    await bus(4,2)
    check((await bus(8)&15)==2,'THRE enable on empty holding register')
    check((await bus(8)&15)==1,'IIR read clears THRE interrupt')
    scoreboard.expect(Frame(0x77))
    monitor=cocotb.start_soon(agent.run_monitor())
    await bus(0,0x77)
    await ClockCycles(d.clk,20)
    check((await bus(8)&15)==2,'THRE re-arms after FIFO drains')
    check((await bus(20)&0x60)==0x20,'THRE precedes TEMT')
    await ClockCycles(d.clk,12*cfg.cycles_per_bit)
    scoreboard.finish();monitor.cancel()
    check((await bus(20)&0x60)==0x60,'Shifter completes')
    await bus(8,7);await bus(4,0);await bus(4,15)
    d.cts_n.value=1
    await agent.send(Frame(0x66))
    check((await bus(8)&15)==4,'RX data outranks THRE and modem IRQ')
    check(await bus(0)==0x66,'Priority test data')
    check((await bus(8)&15)==2,'THRE outranks modem IRQ')
    check((await bus(8)&15)==0,'Modem IRQ follows THRE acknowledgement')
    await bus(24);await bus(4,0)
    # The existing VIP checks each transmitted frame and drives receive data.
    formats=[(4,5,'none',1,0x1f),(0x0d,6,'odd',2,0x15),
             (0x1a,7,'even',1,0x53),(0x0f,8,'odd',2,0x69),
             (0x2b,8,'odd',1,0),(0x2b,8,'even',1,1),
             (0x3b,8,'even',1,0),(0x3b,8,'odd',1,1)]
    matrix_frames=0
    for lcr_value,bits,parity,stops,value in formats:
        await bus(8,7);await bus(12,lcr_value)
        framing=Config(cycles_per_bit=48,data_bits=bits,parity=parity,stop_bits=stops)
        expected=Scoreboard();expected.expect(Frame(value))
        endpoint=CocotbAgent(view,tx='txd',rx='rxd',config=framing,hook=expected.observe)
        watching=cocotb.start_soon(endpoint.run_monitor())
        await bus(0,value)
        await endpoint.send(Frame(value))
        await ClockCycles(d.clk,14*cfg.cycles_per_bit)
        expected.finish();matrix_frames += expected.count;watching.cancel()
        check(await bus(0)==value,'Programmable word length/parity/stop receive')
        check(not (await bus(20)&0x1e),'Configured frame has no RX errors')
    await bus(8,7);await bus(12,4)
    starts=[]
    async def falling_starts():
        from cocotb.utils import get_sim_time
        for _ in range(2):
            await FallingEdge(d.txd)
            starts.append(get_sim_time(unit='ns'))
    capture=cocotb.start_soon(falling_starts())
    expected=Scoreboard();expected.expect(Frame(31));expected.expect(Frame(31))
    endpoint=CocotbAgent(view,tx='txd',rx='rxd',config=Config(cycles_per_bit=48,data_bits=5),hook=expected.observe)
    watching=cocotb.start_soon(endpoint.run_monitor())
    await bus(0,31);await bus(0,31)
    await ClockCycles(d.clk,18*cfg.cycles_per_bit)
    expected.finish();matrix_frames+=expected.count;watching.cancel()
    check(len(starts)==2,'Two five-bit frame starts')
    check(3600<=starts[1]-starts[0]<=3620,'Five-bit 1.5 stop-bit frame period')
    await capture
    Path('uart-checks.json').write_text(json.dumps(dict(checks=checks,tx_frames=scoreboard.count+matrix_frames,
        half_stop_spacing_clocks=(starts[1]-starts[0])/10,seed=31)))
