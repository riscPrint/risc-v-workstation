import pytest
from rvw.vip.coherent import *


def test_directory_data_and_ownership():
    d=Directory()
    for e in sequences():d.observe(e)
    d.finish();assert d.memory[0]==42;assert d.holders[0]=={0};assert d.owner[0]==0
    assert d.credit==[4]*4


def test_snoop_credit_and_data_faults():
    d=Directory(credits=1);d.observe(Event(0,0));
    with pytest.raises(ProtocolError,match='NO_CREDIT'):d.observe(Event(0,1,line=64))
    with pytest.raises(ProtocolError,match='COH_DATA'):d.observe(Event(2,0,data=1))
    d=Directory();d.observe(Event(0,0,0,0,1));d.observe(Event(2,0,0));d.observe(Event(0,1,1,0,1))
    with pytest.raises(ProtocolError,match='INCOMPLETE_SNOOPS'):d.observe(Event(2,1,1))
    d.observe(Event(1,1,0));d.observe(Event(2,1,1));d.finish()
    with pytest.raises(ProtocolError,match='NOT_OWNER'):d.observe(Event(0,2,0,0,2,9))
