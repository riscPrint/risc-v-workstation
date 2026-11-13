from dataclasses import replace
import pytest
from rvw.vip.jtag import *


def test_scan_and_state():
    m=Manager(lambda p:replace(p,tdo=p.tdi));m.reset();sc=Scoreboard()
    for ir in (False,True):
        for value in (0,0xffff,0x7134):sc.observe(value,m.scan(value,16,ir))
    sc.finish();assert m.monitor.state=='RTI'
    assert m.monitor.coverage[('SHIFT_IR','SHIFT_IR')]>0
    with pytest.raises(ProtocolError,match='SCAN_DATA'):sc.observe(1,0)


def test_topology_evidence():
    taps=[Tap('a',5,'in','mid','trst_n',('boundary',)),Tap('b',4,'next','out','reset_test',('embedded',))]
    assert topology(taps)['status']=='inconclusive'
    report=topology(taps,[('mid','next')],[('normal','test')]);assert report['status']=='checked';assert report['total_ir_bits']==9
    assert topology(taps,[],[])['status']=='mismatch'
    with pytest.raises(ValueError):topology([taps[0],taps[0]])
    with pytest.raises(ValueError):Tap('bad',1,'a','b','c')
    with pytest.raises(ProtocolError,match='UNKNOWN'):Monitor().sample(Pins(tms=2))
