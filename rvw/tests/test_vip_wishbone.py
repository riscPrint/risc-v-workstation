import pytest
from rvw.vip.wishbone import *


@pytest.mark.parametrize('seed',[1,17,93])
def test_memory(seed):
    sub=Subordinate(seed);sc=Scoreboard();mon=Monitor(sc.observe)
    def tick(p):p=sub.step(p);mon.sample(p);return p
    manager=Manager(tick)
    for t in sequences(seed):manager.transfer(t)
    mon.finish();sc.finish();assert mon.coverage['wait']>0;assert sc.count==33


def test_bad_data_and_request():
    sub=Subordinate(buggy=True);sc=Scoreboard();mon=Monitor(sc.observe)
    def tick(p):p=sub.step(p);mon.sample(p);return p
    with pytest.raises(ProtocolError,match='READ_DATA'):Manager(tick).transfer(Transfer(0))
    mon=Monitor();mon.sample(Pins(cyc=1,stb=1))
    with pytest.raises(ProtocolError,match='UNSTABLE'):mon.sample(Pins(cyc=1,stb=1,adr=4))
    with pytest.raises(ProtocolError,match='MULTIPLE'):Monitor().sample(Pins(ack=1,err=1))
    with pytest.raises(TimeoutError):Manager(lambda p:p,timeout=2).transfer(Transfer(0))
