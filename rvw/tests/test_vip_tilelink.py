from dataclasses import replace
import pytest
from rvw.vip.tilelink import *


@pytest.mark.parametrize('seed',[1,2,17])
@pytest.mark.parametrize('uh',[False,True])
def test_seeded(seed,uh):
    sc,model=Scoreboard(),Subordinate(seed); mon=Monitor(sc.observe,uh)
    def tick(p):
        p=model.step(p); mon.sample(p); return p
    for request in sequences(seed,uh): Manager(tick).transfer(request)
    mon.finish(); sc.finish()
    assert sc.count==(32 if uh else 9)


def test_bad_dut():
    sc,model=Scoreboard(),Subordinate(buggy=True); mon=Monitor(sc.observe)
    def tick(p):
        p=model.step(p); mon.sample(p); return p
    with pytest.raises(ProtocolError,match='TL_MEMORY_DATA'): Manager(tick).transfer([Request()])


@pytest.mark.parametrize('opcode,param,old,operand,new',[
    (2,0,0xFFFFFFFF,2,0xFFFFFFFF),(2,1,0xFFFFFFFF,2,2),
    (2,2,0xFFFFFFFF,2,2),(2,3,0xFFFFFFFF,2,0xFFFFFFFF),(2,4,0xFFFFFFFF,2,1),
    (3,0,5,3,6),(3,1,5,3,7),(3,2,5,3,1),(3,3,5,3,3)])
def test_atomic(opcode,param,old,operand,new):
    m=Memory(); m.execute([Request(0,data=old)])
    result=m.execute([Request(opcode,param,data=operand)])
    assert result[0].data==old
    assert m.execute([Request()])[0].data==new


def test_same_edge_response_and_source_reuse():
    mon=Monitor()
    mon.sample(Pins(a_valid=1,a_ready=1,d_valid=1,d_ready=1))
    mon.finish()
    mon.sample(Pins(a_valid=1,a_ready=1))
    with pytest.raises(ProtocolError,match='TL_SOURCE_REUSE'): mon.sample(Pins(a_valid=1,a_ready=1))


def test_no_d_interleave_and_source_out_of_order():
    mon=Monitor(uh=True)
    for source in (1,2): mon.sample(Pins(a_valid=1,a_ready=1,a=Request(source=source,size=3)))
    mon.sample(Pins(d_valid=1,d_ready=1,d=Response(source=2,size=3)))
    with pytest.raises(ProtocolError,match='TL_D_INTERLEAVE'):
        mon.sample(Pins(d_valid=1,d_ready=1,d=Response(source=1,size=3)))


def test_early_write_ack_keeps_source_until_last_a():
    mon=Monitor(uh=True); a=Request(0,size=3)
    mon.sample(Pins(a_valid=1,a_ready=1,a=a,d_valid=1,d_ready=1,d=Response(0,size=3)))
    assert 0 in mon.pending
    mon.sample(Pins(a_valid=1,a_ready=1,a=a)); mon.finish()


@pytest.mark.parametrize('req,code',[(Request(2),'TL_PROFILE'),(Request(size=3),'TL_PROFILE'),
    (Request(address=1),'TL_ALIGNMENT'),(Request(mask=0),'TL_MASK'),(Request(param=1),'TL_PARAM')])
def test_request_errors(req,code):
    with pytest.raises(ProtocolError,match=code): check_request(req)


def test_denied_and_corrupt():
    mon=Monitor(); mon.sample(Pins(a_valid=1,a_ready=1))
    with pytest.raises(ProtocolError,match='TL_D_CORRUPT'):
        mon.sample(Pins(d_valid=1,d=Response(denied=True)))
    m=Memory()
    assert m.execute([Request(0,corrupt=True)])[0].denied
    assert not m.bytes


def test_message_control_and_drain():
    mon=Monitor(uh=True); a=Request(0,size=3)
    mon.sample(Pins(a_valid=1,a_ready=1,a=a))
    with pytest.raises(ProtocolError,match='TL_A_MESSAGE_CONTROL'):
        mon.sample(Pins(a_valid=1,a_ready=1,a=replace(a,address=8)))
    with pytest.raises(ProtocolError,match='TL_OUTSTANDING'): mon.finish()
    mon.sample(Pins(reset_n=0)); mon.finish()


def test_manager_finishes_a_after_early_ack():
    sent=[]
    def tick(p):
        sent.append(p.a)
        return replace(p,a_ready=1,d_valid=int(len(sent)==1),d=Response(0,size=3))
    result=Manager(tick).transfer([Request(0,size=3),Request(0,size=3,data=7)])
    assert len(sent)==2 and len(result)==1


def test_narrow_atomic_lanes():
    model=Memory(); model.execute([Request(0,data=0x11223344)])
    old=model.execute([Request(3,3,size=0,address=1,mask=2,data=0xAA00)])
    assert old[0].data==0x11223344
    assert model.execute([Request()])[0].data==0x1122AA44


def test_driven_readiness_and_d_hold():
    model=Subordinate(2)
    p=Pins(a_valid=1)
    model.step(p,driven=Pins(a_ready=0))
    assert not model.messages
    model.step(p,driven=Pins(a_ready=1))
    first=model.step(Pins(),commit=False)
    second=model.step(Pins(),commit=False)
    assert first.d_valid and first.d==second.d


def test_zero_latency_valid_without_acceptance():
    mon=Monitor()
    mon.sample(Pins(a_valid=1,d_valid=1))
    mon.finish()
    with pytest.raises(ProtocolError,match='TL_D_BEFORE_A'):
        mon.sample(Pins(a_valid=1,d_valid=1,d_ready=1))


def test_different_sources_complete_out_of_order():
    events=[]; mon=Monitor(events.append)
    for source in (1,2): mon.sample(Pins(a_valid=1,a_ready=1,a=Request(source=source)))
    for source in (2,1): mon.sample(Pins(d_valid=1,d_ready=1,d=Response(source=source)))
    mon.finish()
    assert [event[0][0].source for event in events]==[2,1]
