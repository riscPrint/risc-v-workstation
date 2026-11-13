"""Native peripheral scenarios on the map-driven SpinalSoc composition."""
import json
from pathlib import Path
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, ClockCycles, Timer
import pyuvm
from rvw.uvm.scenarios import SocScenarios


class Backend:
    def __init__(self,dut):
        self.d=dut; self.traffic=None; self.pending_before_reset=False; self.aborted=False
    async def wait_cycles(self,count):
        await ClockCycles(self.d.clk,count)
        await FallingEdge(self.d.clk)
    async def reset(self):
        if self.traffic is not None:
            self.pending_before_reset=bool(int(self.d.busy.value))
            self.traffic.cancel(); self.aborted=self.pending_before_reset
        self.d.start.value=0; self.d.reset.value=1
        await self.wait_cycles(5)
        assert int(self.d.busy.value)==0 and int(self.d.done.value)==0, 'SOC_RESET_BUSY'
        self.d.reset.value=0
        await self.wait_cycles(2)
    async def irq(self,mask):
        assert mask in (0,1<<11)
        await FallingEdge(self.d.clk); self.d.control_requestIrq.value=int(bool(mask))
        await self.wait_cycles(2)
        assert int(self.d.observedIrqs.value)==mask, 'SOC_IRQ_ROUTING'
    async def wait_interrupt(self,cause):
        assert int(self.d.observedIrqs.value)==1<<cause, 'SOC_IRQ_CAUSE'
        return dict(cause=cause,checks=1)
    async def inject_bus_error(self,enable):
        await FallingEdge(self.d.clk); self.d.control_injectError.value=int(enable)
    async def transfer(self,request):
        await FallingEdge(self.d.clk)
        self.d.address.value=request.get('address',0x10000000)
        self.d.write.value=int(request.get('write',False))
        self.d.data.value=request.get('data',0)
        self.d.start.value=1
        for _ in range(100):
            await RisingEdge(self.d.clk); await Timer(1,unit='ns')
            if int(self.d.done.value):break
        else:raise AssertionError('SOC_TRANSFER_WATCHDOG')
        result=dict(checks=1,error=bool(int(self.d.error.value)),data=int(self.d.readData.value))
        await FallingEdge(self.d.clk); self.d.start.value=0
        await self.wait_cycles(2)
        return result
    async def start_traffic(self):
        self.d.control_hold.value=1
        self.traffic=cocotb.start_soon(self.transfer(dict(write=True,data=0xdeadbeef)))
        return self.traffic
    async def traffic_pending(self,handle):
        return int(self.d.busy.value)==1 and not int(self.d.done.value) and not handle.done()
    async def check_reset(self,handle):
        assert self.aborted and self.pending_before_reset, 'SOC_MISSING_ABORT'
        assert not int(self.d.busy.value) and not int(self.d.done.value), 'SOC_PENDING_AFTER_RESET'
        self.d.control_hold.value=0
        result=await self.transfer({})
        assert not result['error'] and result['data']==0x1234, 'SOC_RESET_DATA'
        return dict(checks=3,aborted=True)
    async def stop_traffic(self,handle):
        if not handle.done():handle.cancel()
        self.d.control_hold.value=0;self.d.start.value=0;self.traffic=None


class ScenarioTest(pyuvm.uvm_test):
    seed=1
    async def run_phase(self):
        self.raise_objection()
        d=cocotb.top
        for name in ('start','address','write','data','control_hold','control_injectError','control_requestIrq'):
            getattr(d,name).value=0
        d.reset.value=1
        clock=cocotb.start_soon(Clock(d.clk,10,unit='ns').start())
        backend=Backend(d); scenarios=SocScenarios(backend,seed=self.seed)
        try:
            await backend.reset()
            initial=await backend.transfer({})
            assert initial['data']==0x1234 and not initial['error'], 'SOC_INITIAL_RESET'
            storm=await scenarios.interrupt_storm([11],count=32)
            error=await scenarios.bus_error(dict(write=True,data=0x55555555))
            read=await backend.transfer({})
            assert not read['error'] and read['data']==0x1234, 'SOC_ERROR_SIDE_EFFECT'
            reset=await scenarios.reset_during_traffic(delay=4)
            Path(f'scenarios-{self.seed}.json').write_text(json.dumps(dict(
                scope='SpinalSoc APB fabric and peripheral IRQ routing; no CPU execution',
                interrupt_storm=storm,bus_error=error,reset_during_traffic=reset,cpu_checks=0),indent=2)+'\n')
        finally:
            clock.cancel();self.drop_objection()


for seed in (1,7):
    globals()[f'Scenarios{seed}']=pyuvm.test()(type(f'Scenarios{seed}',(ScenarioTest,),{'seed':seed,'__module__':__name__}))
