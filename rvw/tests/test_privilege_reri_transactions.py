import pytest
from rvw.privilege import campaign
from rvw.privilege.reri_transactions import programs,reference,apply,Device
from rvw.privilege.reri import Record,RDIP,CECO

pytestmark=pytest.mark.fast


def test_transactions_and_model():
    c=campaign.load('examples/privilege/reri-transactions.json');rows=campaign.scenarios(c)
    assert len(rows)==7 and len({r['id'] for r in rows})==7
    assert all(reference(r)['status']=='pass' for r in rows)
    overflow=next(r for r in rows if r['id'].endswith('counter-overflow'))
    result=reference(overflow)
    assert any(int(v,0)&CECO for v in result['actual'])
    assert result['signals']==[dict(severity=1,signal=1)]
    increment=next(r for r in rows if r['id'].endswith('counter-increment'))
    assert not reference(increment)['signals']


@pytest.mark.parametrize('initial',[0,1,0xffffffffffffffff,0xa000010007])
def test_initial_record_state_is_not_assumed(initial):
    c=campaign.load('examples/privilege/reri-transactions.json')
    for row in programs(c):
        plan=row['reference_model'];m=Record(status=initial);values=[]
        assert plan['actions'][0]['observe'] is False
        for action in plan['actions']:
            apply(m,action)
            if action['observe']:values.append(hex(m.status&int(plan['mask'],0)))
        assert values==plan['expected']


def test_counter_capability_is_explicit():
    c=campaign.load('examples/privilege/reri-transactions.json');c['reri'].pop('ce_counter_bits')
    assert len(programs(c))==3
    c['reri']['ce_counter_bits']=8
    with pytest.raises(ValueError,match='16-bit'):programs(c)


def test_device_only_accepts_the_declared_register_accesses():
    d=Device(0x30000000)
    d.write(0x30000040,1,8);d.event(dict(kind='reri-error',record=0,status=2))
    before=d.read(0x30000048,8)
    d.write(0x30000048,0,8);assert d.read(0x30000048,8)==before
    d.write(0x30000040,1|(1<<48)|(1<<49),8)
    assert not d.read(0x30000048,8)&1
    with pytest.raises(ValueError):d.read(0x30000048,4)
