from copy import deepcopy
import pytest
from rvw.privilege import campaign,spike_aplic

pytestmark=pytest.mark.fast


def device(profile='aplic'):
    c=campaign.load('examples/privilege/'+profile+'.json');return c,spike_aplic.Device(c)


def test_priority_threshold_and_read_only_topi():
    c,d=device();base=c['aplic']['base'];claim=base+0x401c
    for source,priority in ((1,3),(2,1)):
        d.write(base+4*source,1,4);d.write(base+0x3000+4*source,priority,4)
    d.write(base+0x1e00,6,4);d.write(base+0x1c00,6,4)
    assert d.read(base+0x4018,4)==0x20001
    assert d.read(base+0x4018,4)==0x20001
    assert deepcopy(d).read(claim,4)==0x20001
    assert d.read(claim,4)==0x20001
    d.write(base+0x4008,2,4);assert d.read(claim,4)==0
    d.write(base+0x4008,0,4);assert d.read(claim,4)==0x10003
    assert d.read(claim,4)==0
    assert d.read(base+0x1f00,4)==0 and d.read(base+0x1d00,4)==0


def test_target_context_and_uninitialized_target_are_explicit():
    c,d=device();b=c['aplic']['base']
    d.write(b+4,1,4);d.write(b+0x1e00,2,4);d.write(b+0x1c00,2,4)
    with pytest.raises(ValueError,match='target not initialized'):d.read(b+0x401c,4)
    d.write(b+0x3004,(2<<18)|1,4)
    assert d.read(b+0x401c,4)==0 and d.read(b+0x405c,4)==0x10001


def test_delegated_and_revoked_register_state():
    c,d=device('aplic-delegation');b=c['aplic']['parent_base'];child=c['aplic']['child_base'];source=33
    d.write(b+source*4,0x400,4);assert d.read(b+source*4,4)==0x400
    d.write(b+0x1e04,2,4);d.write(b+0x1c04,2,4)
    assert d.read(b+0x1e04,4)==0 and d.read(b+0x1c04,4)==0
    d.write(child+source*4,1,4);d.write(child+0x3000+source*4,1,4)
    d.write(child+0x1e04,2,4);d.write(child+0x1c04,2,4)
    assert d.read(child+0x401c,4)==0x210001
    d.write(b+source*4,1,4);assert d.read(child+source*4,4)==0
    d.write(b+source*4,0x400,4);assert d.read(child+source*4,4)==0


@pytest.mark.parametrize('size',[1,2,8])
def test_unsupported_access_shapes_fail_closed(size):
    c,d=device()
    with pytest.raises(ValueError,match='32-bit'):d.read(c['aplic']['base'],size)


def test_wire_and_msi_modes_are_not_silently_approximated():
    c,d=device();b=c['aplic']['base']
    with pytest.raises(ValueError,match='Detached'):d.write(b+4,4,4)
    with pytest.raises(ValueError,match='direct delivery'):d.write(b,0x104,4)


@pytest.mark.parametrize('field,value',[('spec_version','future'),('spec_revision','future')])
def test_native_model_requires_the_selected_specification(field,value):
    c=campaign.load('examples/privilege/aplic.json');c[field]=value
    with pytest.raises(ValueError):spike_aplic.Device(c)
