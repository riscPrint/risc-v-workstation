"""Seeded pin requests do not claim architectural interrupt/debug behavior."""
import asyncio
import pytest
from rvw.sim.cpu_env import CpuControls


def controller(seed=3):
    events = []
    async def wait(cycles): events.append(('wait', cycles))
    controls = CpuControls(wait, lambda value: events.append(('reset',value)),
        lambda value: events.append(('irq',value)), lambda value: events.append(('debug',value)),seed=seed)
    return controls,events


def test_reset_order():
    controls, events = controller()
    asyncio.run(controls.reset())
    assert events == [('irq',0),('debug',0),('reset',True),('wait',5),('reset',False)]


def test_random_requests_are_seeded_and_masked():
    a, events = controller(); b, other = controller()
    asyncio.run(a.random_requests(30,0x888)); asyncio.run(b.random_requests(30,0x888))
    assert events == other
    assert any(k=='irq' and v for k,v in events)
    assert any(k=='debug' and v for k,v in events)
    assert all(value & ~0x888 == 0 for key,value in events if key=='irq')
    assert events[-2:] == [('irq',0),('debug',0)]


@pytest.mark.parametrize('count,mask,gap',[(0,8,1),(1,0,1),(1,2**32,1),(1,8,0)])
def test_invalid_control_bounds(count,mask,gap):
    controls, events = controller()
    with pytest.raises(ValueError): asyncio.run(controls.random_requests(count,mask,gap))
    assert not events


def test_control_failure_clears_requests():
    events=[]
    async def broken_wait(cycles): raise RuntimeError('stopped')
    controls=CpuControls(broken_wait,lambda value: None,
        lambda value: events.append(('irq',value)),lambda value: events.append(('debug',value)))
    with pytest.raises(RuntimeError): asyncio.run(controls.random_requests(1,8))
    assert events == [('irq',0),('debug',0)]
