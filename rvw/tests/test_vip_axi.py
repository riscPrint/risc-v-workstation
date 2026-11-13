from dataclasses import replace
import pytest
from rvw.vip.axi import (Address, Write, Response, Pins, Monitor, Manager,
                         Subordinate, Scoreboard, ProtocolError, sequences, inject, check_address)


@pytest.mark.parametrize('seed', [1, 2, 17])
@pytest.mark.parametrize('lite', [False, True])
def test_seeded_memory(seed, lite):
    model, sc = Subordinate(seed), Scoreboard()
    mon = Monitor(sc.observe, lite)
    def tick(p):
        p = model.step(p); mon.sample(p); return p
    manager = Manager(tick)
    for a, beats in sequences(seed, lite):
        manager.write(a, beats)
        manager.read(a)
    mon.finish()
    assert sc.count == (2 if lite else 28)
    if not lite: assert mon.coverage['stall', 'ar'] or mon.coverage['stall', 'aw']


def test_buggy_read():
    model, sc = Subordinate(buggy=True), Scoreboard()
    mon = Monitor(sc.observe)
    def tick(p):
        p = model.step(p); mon.sample(p); return p
    with pytest.raises(ProtocolError, match='AXI_READ_DATA'):
        Manager(tick).read(Address())


@pytest.mark.parametrize('ch', ['aw', 'w', 'b', 'ar', 'r'])
def test_stability(ch):
    mon = Monitor()
    # B/R need a prior outstanding transaction.
    mon.sample(Pins(awvalid=1, awready=1, wvalid=1, wready=1, arvalid=1, arready=1))
    p = Pins(**{ch+'valid':1})
    mon.sample(p)
    with pytest.raises(ProtocolError, match='AXI_STABLE_'+ch.upper()):
        mon.sample(inject(p, ch))


def test_out_of_order_ids_and_write_before_address():
    got=[]; mon=Monitor(got.append)
    mon.sample(Pins(wvalid=1,wready=1))
    mon.sample(Pins(awvalid=1,awready=1,aw=Address(id=3),arvalid=1,arready=1,ar=Address(id=1)))
    mon.sample(Pins(arvalid=1,arready=1,ar=Address(id=2)))
    mon.sample(Pins(rvalid=1,rready=1,r=Response(id=2)))
    mon.sample(Pins(rvalid=1,rready=1,r=Response(id=1),bvalid=1,bready=1,b=Response(id=3)))
    mon.finish()
    assert [event[1].id for event in got] == [2,3,1]


def test_exclusive_success_and_invalidation():
    model=Subordinate(17); mon=Monitor(); sc=Scoreboard()
    mon.hook=sc.observe
    def tick(p):
        p=model.step(p); mon.sample(p); return p
    m=Manager(tick); a=Address(0x100,id=2,lock=1)
    assert m.read(a)[0].response==1
    assert m.write(a,[Write(42)]).response==1
    assert m.write(a,[Write(99)]).response==0
    m.read(a)
    m.write(Address(0x100,id=3),[Write(7)])
    assert m.write(a,[Write(99)]).response==0
    assert m.read(Address(0x100))[0].data==7
    mon.finish()


@pytest.mark.parametrize('a,code', [
    (Address(4092,length=1),'AXI_4K_BOUNDARY'),
    (Address(length=2,burst=2),'AXI_BURST_LENGTH'),
    (Address(4,length=1,lock=1),'AXI_EXCLUSIVE_ALIGNMENT'),
    (Address(1),'AXI_UNALIGNED_PROFILE')])
def test_bad_address(a,code):
    with pytest.raises(ProtocolError,match=code): check_address(a)


@pytest.mark.parametrize('pins,code', [
    (Pins(bvalid=1),'AXI_B_WITHOUT_WRITE'), (Pins(rvalid=1),'AXI_R_WITHOUT_READ'),
    (Pins(awvalid=1,awready=1,wvalid=1,wready=1,w=Write(last=False)),'AXI_WLAST'),
    (Pins(awvalid=1,awready=1,aw=Address(size=0),wvalid=1,wready=1),'AXI_WSTRB_LANE')])
def test_bad_transfers(pins,code):
    with pytest.raises(ProtocolError,match=code): Monitor().sample(pins)


def test_drain_and_reset():
    mon=Monitor()
    mon.sample(Pins(arvalid=1,arready=1))
    with pytest.raises(ProtocolError,match='AXI_OUTSTANDING'): mon.finish()
    mon.sample(Pins(reset_n=0)); mon.finish()
    with pytest.raises(ProtocolError,match='AXIL_PROFILE'): check_address(Address(id=1),True)


def test_subordinate_uses_driven_readiness_and_holds_response():
    model=Subordinate(4)
    # Cocotb uses a separate drive phase and commit phase.
    p=Pins(arvalid=1,ar=Address())
    driven=replace(model.step(p,commit=False),arready=0)
    model.step(p,driven=driven)
    assert not any(model.rs.values())
    driven=replace(model.step(p,commit=False),arready=1)
    model.step(p,driven=driven)
    first=model.step(Pins(rready=0))
    second=model.step(Pins(rready=0))
    assert first.rvalid and first.r==second.r


def test_read_id_order_and_last_failure():
    mon=Monitor()
    mon.sample(Pins(arvalid=1,arready=1,ar=Address(length=1)))
    with pytest.raises(ProtocolError,match='AXI_RLAST'):
        mon.sample(Pins(rvalid=1,r=Response(last=True)))


def test_reset_reuses_seed_and_clears_memory():
    model=Subordinate(17)
    first=model.step(Pins())
    model.memory[0]=42
    model.step(Pins(reset_n=0))
    assert model.step(Pins())==first
    assert not model.memory
