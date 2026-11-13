from dataclasses import replace
import pytest
from rvw.vip.clock_reset import *


@pytest.mark.parametrize('half,hold',[(1,1),(5,2),(10,4)])
def test_waveform(half,hold):
    m=Manager(lambda p:p,Config(half,hold));m.run(12)
    assert m.monitor.coverage['edges']==24
    assert m.monitor.coverage['reset_release']==1


def test_bad_clock_and_reset():
    m=Monitor();m.sample(Pins(0,0,0))
    with pytest.raises(ProtocolError,match='HALF_PERIOD'):m.sample(Pins(4,1,0))
    m=Monitor();m.sample(Pins(0,0,0));m.sample(Pins(5,1,0))
    with pytest.raises(ProtocolError,match='TOO_SHORT'):m.sample(Pins(10,0,1))
    m=Monitor();m.sample(Pins(0,0,0))
    with pytest.raises(ProtocolError,match='RELEASE_EDGE'):m.sample(Pins(5,1,1))
    with pytest.raises(ProtocolError,match='NO_SEQUENCE'):Monitor().finish()
    with pytest.raises(ValueError):Config(0)
