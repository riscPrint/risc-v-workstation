import pytest
from rvw.vip.gpio import *


@pytest.mark.parametrize('latency',[0,1,2,4])
def test_direction_sync_and_reset(latency):
    c=Config(width=4,sync_cycles=latency,rising=1,falling=2,high=4,low=8)
    ref=Reference(c); manager=Manager(ref.step,c)
    for p in sequences(7,config=c): manager.drive(p)
    for _ in range(latency+1): out=manager.drive(Pins(external=15))
    assert out.sampled==15 and out.irq==4
    manager.drive(Pins(reset_n=0))
    assert manager.monitor.coverage['direction_change']>0


def test_independent_expected_edges():
    ref=Reference(Config(width=4,sync_cycles=1,rising=1,falling=2,high=4,low=8))
    assert ref.step(Pins(external=15)).sampled==0
    p=ref.step(Pins(external=0)); assert (p.sampled,p.irq)==(15,5)
    p=ref.step(Pins(external=0)); assert (p.sampled,p.irq)==(0,10)
    p=ref.step(Pins(external=0)); assert p.irq==8


def test_fault_and_unknown():
    with pytest.raises(ProtocolError,match='STATE_OR_IRQ'): Manager(lambda p: inject(Reference().step(p))).drive(Pins())
    with pytest.raises(ProtocolError,match='UNKNOWN_OR_WIDE'): Reference().step(Pins(external=-1))
    with pytest.raises(ValueError): Config(width=0)
    with pytest.raises(ValueError): Config(rising=256)
    with pytest.raises(ProtocolError,match='NO_SAMPLES'): Scoreboard().finish()
