import pytest
from rvw.privilege.controllers import Imsic, Aplic, NestedPriority, Aclint


pytestmark = pytest.mark.fast


def test_imsic_delivery_threshold_and_claim():
    m=Imsic(); m.enabled={1,2};m.inject(2);m.inject(1)
    assert m.top()==1 and not m.irq
    m.delivery=True;assert m.irq
    m.threshold=1;assert m.top()==0
    m.threshold=2;assert m.claim()==1 and m.top()==0
    m.threshold=0;assert m.claim()==2 and m.claim()==0
    m.inject(0);m.inject(64);assert not m.pending


def test_imsic_indirect_files():
    a,b=Imsic(),Imsic();a.indirect(0xc0,6);a.inject(2)
    assert a.indirect(0x80)==4 and b.indirect(0x80)==0
    assert a.claim()==2
    with pytest.raises(ValueError):a.indirect(0x81)


def test_aplic_source_modes_and_msi():
    a=Aplic();a.configure(1,4);a.configure(2,6);a.enabled={1,2}
    a.priority={1:2,2:1};a.set_level(1,True);a.set_level(2,True)
    assert a.claim()==2 and a.claim()==2
    a.set_level(2,False);assert a.claim()==1 and a.claim()==0
    a.configure(1,1);a.pending.add(1);a.targets[1]=(3,17)
    assert a.msi()==[(3,17)] and a.msi()==[]


def test_aplic_threshold_and_delegation():
    a=Aplic();child=Aplic();a.children[1]=child
    child.configure(1,4);child.enabled={1};a.set_level(1,True)
    assert a.top()==0 and child.top()==1
    child.threshold=1;assert child.top()==0


def test_nested_priority_save_restore():
    m=NestedPriority();assert m.eligible(255)
    m.trap(16);assert not m.eligible(16) and m.eligible(15)
    saved=m.previous
    m.trap();assert m.threshold==16
    m.ret();assert m.threshold==16
    m.restore_previous(saved);m.ret();assert m.threshold==256
    m=NestedPriority(8,4);m.threshold=0x2f
    assert not m.eligible(0x20) and m.eligible(0x1f)


def test_aclint_set_only_sswi():
    m=Aclint(2);m.set_ssip(1,1);m.set_ssip(1,0)
    assert m.ssip==[False,True]
    m.clear_ssip_csr(1);assert not m.ssip[1]
    m.write_msip(0,3);assert m.msip[0]
    m.write_msip(0,2);assert not m.msip[0]
    m.compare[0]=10;m.tick(9);assert not m.mtip(0)
    m.tick();assert m.mtip(0)


def test_inactive_and_delegated_sources_are_not_delivered():
    a=Aplic();a.configure(1,1);a.pending={1};a.enabled={1};a.targets[1]=(0,17)
    a.configure(1,0)
    assert not a.pending and not a.enabled and 1 not in a.targets
    a.configure(1,1);a.pending={1};a.enabled={1};a.children[1]=Aplic()
    assert a.top()==0 and a.msi()==[]


def test_no_implicit_threshold_stack():
    m=NestedPriority();m.trap(16);m.trap(8)
    m.ret();assert m.threshold==16
    m.ret();assert m.threshold==16
