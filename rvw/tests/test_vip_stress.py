import pytest
from rvw.vip.stress import *


@pytest.mark.parametrize('bandwidth,refresh',[(1,0),(2,3)])
def test_latency_bandwidth_refresh_and_qos(bandwidth,refresh):
    c=Config(bandwidth=bandwidth,refresh_cycles=refresh)
    m=Manager(Subordinate(17,c),c);report=m.run(sequences(17,64,c))
    assert report['responses']==64
    assert all(report[('qos',i)] for i in range(4))
    assert report['latency_sum']>=128


def test_errors_starvation_and_credit():
    c=Config();m=Manager(Subordinate(config=c),c)
    assert m.run([Request(0,address=64)])['errors']==1
    with pytest.raises(ProtocolError,match='RESPONSE_DATA'):Manager(Subordinate(buggy=True)).run([Request(0)])
    mon=Monitor(Config(credits=1));mon.request(Request(0),0)
    with pytest.raises(ProtocolError,match='NO_CREDIT'):mon.request(Request(1),0)
    with pytest.raises(ProtocolError,match='STARVATION'):mon.advance(33)
