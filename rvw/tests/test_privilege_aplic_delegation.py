from copy import deepcopy
import pytest
from rvw.privilege import campaign,aplic_delegation as delegation

pytestmark=pytest.mark.fast


def test_domain_ownership_and_claim_sequences():
    rows=campaign.scenarios(campaign.load('examples/privilege/aplic-delegation.json'))
    assert len(rows)==2 and all(delegation.reference(r)['status']=='pass' for r in rows)
    for row in rows:
        plan=row['reference_model'];claims=[v for op,v in zip([o for o in plan['operations'] if o['op']=='read'],plan['expected']) if op['register']=='claim']
        claimed=(plan['source']<<16)|1
        assert claims==[0,claimed,0,0,claimed,0,0,claimed,0]
        assert len(row['bins'])==3 and row['reference_mode']=='model-observations'
        altered=deepcopy(row);altered['reference_model']['expected'][1]=1
        assert delegation.reference(altered)['status']=='fail'
    one=rows[0]['reference_model'];two=rows[1]['reference_model']
    assert delegation.address(two,'child','ip')==delegation.address(one,'child','ip')+4


def test_parent_and_unowned_child_writes_are_ignored():
    plan=campaign.scenarios(campaign.load('examples/privilege/aplic-delegation.json'))[0]['reference_model'];m=delegation.Domains(plan)
    m.execute(dict(op='route',value=True))
    for reg in ('ie','ip'):m.execute(dict(op='write',domain='root',register=reg,value=2))
    assert m.execute(dict(op='read',domain='root',register='ie'))==0
    assert m.execute(dict(op='read',domain='root',register='ip'))==0
    m.execute(dict(op='write',domain='child',register='cfg',value=1))
    m.execute(dict(op='route',value=False))
    assert m.execute(dict(op='read',domain='child',register='cfg'))==0
    m.execute(dict(op='route',value=True))
    assert m.execute(dict(op='read',domain='child',register='cfg'))==0


@pytest.mark.parametrize('field,value',[('direct_delivery',False),('implemented_sources',0),('source_ids',[34]),('child_base',0xd000000),('child_index',1024)])
def test_invalid_hierarchy(field,value):
    c=campaign.load('examples/privilege/aplic-delegation.json');c['aplic'][field]=value
    with pytest.raises(ValueError):campaign.scenarios(c)
