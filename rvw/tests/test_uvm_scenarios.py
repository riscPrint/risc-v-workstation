import asyncio
import pytest
from rvw.uvm.scenarios import SocScenarios
pytestmark=pytest.mark.fast

class Backend:
    def __init__(self): self.irqs=[];self.injection=[];self.stopped=False;self.cause_offset=0
    async def reset(self): pass
    async def boot(self): return dict(checks=2)
    async def wait_cycles(self,n): pass
    async def irq(self,mask): self.irqs.append(mask)
    async def wait_interrupt(self,cause): return dict(checks=1,cause=cause+self.cause_offset)
    async def inject_bus_error(self,on): self.injection.append(on)
    async def transfer(self,request): return dict(checks=1,error=self.error)
    async def start_traffic(self): return 1
    async def traffic_pending(self,handle): return self.pending
    async def check_reset(self,handle): return dict(checks=1,aborted=True)
    async def stop_traffic(self,handle): self.stopped=True


def test_boot_and_seeded_interrupt_storm():
    first,second=Backend(),Backend()
    async def run(b):
        scenarios=SocScenarios(b,seed=17)
        assert (await scenarios.boot())['checks']==2
        assert await scenarios.interrupt_storm([3,7,11],count=8)==dict(checks=8,interrupts=8)
    asyncio.run(run(first));asyncio.run(run(second))
    assert first.irqs==second.irqs
    assert all(mask in (0,1<<3,1<<7,1<<11) for mask in first.irqs)
    assert first.irqs[-1]==0


def test_wrong_irq_cause_clears_request():
    b=Backend();b.cause_offset=1
    with pytest.raises(AssertionError,match='INTERRUPT_CAUSE'):
        asyncio.run(SocScenarios(b).interrupt_storm([3]))
    assert b.irqs[-1]==0


@pytest.mark.parametrize('error',[True,False])
def test_bus_error_is_observed_and_injection_restored(error):
    b=Backend();b.error=error
    if error: assert asyncio.run(SocScenarios(b).bus_error(0x1000))['error']
    else:
        with pytest.raises(AssertionError,match='MISSING_BUS_ERROR'):
            asyncio.run(SocScenarios(b).bus_error(0x1000))
    assert b.injection==[True,False]


@pytest.mark.parametrize('pending',[True,False])
def test_reset_requires_live_traffic_and_cleans_task(pending):
    b=Backend();b.pending=pending
    if pending: assert asyncio.run(SocScenarios(b).reset_during_traffic())['aborted']
    else:
        with pytest.raises(AssertionError,match='NO_PENDING_TRAFFIC'):
            asyncio.run(SocScenarios(b).reset_during_traffic())
    assert b.stopped


def test_empty_project_report_cannot_pass():
    with pytest.raises(AssertionError,match='NO_CHECKS'): SocScenarios.checked(dict(checks=0))
