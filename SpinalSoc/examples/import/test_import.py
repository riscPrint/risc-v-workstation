"""Use imported UART registers and pins through the actual composer fabric."""
import json
from pathlib import Path
from types import SimpleNamespace
import cocotb
from cocotb.triggers import FallingEdge,RisingEdge,ClockCycles
from rvw.sim.bench import start
from rvw.vip.uart import CocotbAgent,Config,Frame,Scoreboard


@cocotb.test()
async def imported_uart(d):
    checks=0
    def check(condition,message):
        nonlocal checks
        assert condition,message
        checks+=1
    async def bus(offset,data=None):
        await FallingEdge(d.clk)
        d.core_stimulus_valid.value=1;d.core_stimulus_address.value=0x10000000+offset
        d.core_stimulus_write.value=int(data is not None)
        d.core_stimulus_wdata.value=data or 0;d.core_stimulus_mask.value=15
        for _ in range(200):
            await RisingEdge(d.clk)
            if int(d.core_stimulus_ready.value):break
        else:raise AssertionError('IMPORTED_WISHBONE_ACK_TIMEOUT')
        check(not int(d.core_stimulus_error.value),'IMPORTED_BUS_ERROR')
        value=int(d.core_stimulus_rdata.value) if data is None else None
        await FallingEdge(d.clk);d.core_stimulus_valid.value=0
        return value
    for field in ('valid','address','write','wdata','mask'):getattr(d,'core_stimulus_'+field).value=0
    d.external_uart_srx_pad_i.value=1
    for pin in ('cts','dsr','ri','dcd'):getattr(d,'external_uart_'+pin+'_pad_i').value=1
    await start(d)
    for value in (0x5a,0xa5,0):
        await bus(28,value);check(await bus(28)==value,'EXTERNAL_SCRATCH_READBACK')
    await bus(12,0x83);await bus(0,2);await bus(4,0)
    check(await bus(0)==2,'EXTERNAL_DIVISOR')
    await bus(12,3);await bus(8,6)
    class Reset:
        @property
        def value(self):return 1-int(d.reset.value)
    view=SimpleNamespace(clk=d.clk,reset_n=Reset(),tx=d.external_uart_stx_pad_o,rx=d.external_uart_srx_pad_i)
    board=Scoreboard();agent=CocotbAgent(view,tx='tx',rx='rx',config=Config(cycles_per_bit=32),hook=board.observe)
    monitor=cocotb.start_soon(agent.run_monitor())
    for value in (0xa6,0x39):board.expect(Frame(value));await bus(0,value)
    await ClockCycles(d.clk,800);board.finish();check(board.count==2,'EXTERNAL_UART_TX')
    await agent.send(Frame(0x5c));await ClockCycles(d.clk,40)
    check(bool(await bus(20)&1),'EXTERNAL_UART_RX_READY')
    check(await bus(0)==0x5c,'EXTERNAL_UART_RX_DATA')
    monitor.cancel()
    Path('import-checks.json').write_text(json.dumps(dict(checks=checks,tx_frames=board.count,rx_frames=1,bus='wishbone',cpu_executed=False),indent=2)+'\n')
