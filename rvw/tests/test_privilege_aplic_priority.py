from copy import deepcopy
import pytest
from rvw.privilege import campaign,aplic_priority,aia,spike_aplic

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('bits',[1,2,3,8])
def test_priority_conversion_and_legal_threshold_boundaries(bits):
    c=campaign.load('examples/privilege/aplic-priority.json');c['aplic']['priority_bits']=bits
    row=campaign.scenarios(c)[0]
    assert aplic_priority.reference(row)['status']=='pass'
    p=row['reference_model'];reads=[a for a in p['actions'] if a['op']=='read']
    values=[v for a,v in zip(reads,p['expected']) if a['register']=='target']
    assert 1 in values and (1<<bits)-1 in values
    if bits==1:assert set(values)=={1}
    altered=deepcopy(row);altered['reference_model']['expected'][0]=0
    assert aplic_priority.reference(altered)['status']=='fail'
    c=campaign.load('examples/privilege/aplic.json');c['aplic']['priority_bits']=bits
    rows=campaign.scenarios(c)
    assert all(aia.reference(r)['status']=='pass' for r in rows)
    if bits==1:
        assert next(r for r in rows if r['id']=='aplic-priority')['reference_model']['expected']==[1,2,0]
        assert next(r for r in rows if r['id']=='aplic-threshold')['reference_model']['expected']==[0,0,0]


def test_native_one_bit_priority_and_threshold():
    c=campaign.load('examples/privilege/aplic.json');c['aplic']['priority_bits']=1;d=spike_aplic.Device(c);base=c['aplic']['base']
    d.write(base+4,1,4);d.write(base+0x3004,0xff,4)
    assert d.read(base+0x3004,4)==1
    d.write(base+0x1e00,2,4);d.write(base+0x1c00,2,4);d.write(base+0x4008,1,4)
    assert d.read(base+0x401c,4)==0
    d.write(base+0x4008,0,4);assert d.read(base+0x401c,4)==0x10001


@pytest.mark.parametrize('bits',[0,9,True])
def test_invalid_priority_width(bits):
    c=campaign.load('examples/privilege/aplic-priority.json');c['aplic']['priority_bits']=bits
    with pytest.raises(ValueError):campaign.scenarios(c)


def test_reserved_wlrl_threshold_value_is_not_predicted():
    c=campaign.load('examples/privilege/aplic.json');c['aplic']['priority_bits']=1;d=spike_aplic.Device(c)
    with pytest.raises(ValueError,match='WLRL threshold'):d.write(c['aplic']['base']+0x4008,2,4)
