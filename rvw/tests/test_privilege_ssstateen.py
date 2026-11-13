from copy import deepcopy
import pytest
from rvw.privilege import campaign,ssstateen

pytestmark=pytest.mark.fast


def test_no_machine_bank_and_complete_expected_plans():
    for name,count in [('ssstateen-only',24),('ssstateen-only-h',80)]:
        c=campaign.load('examples/privilege/'+name+'.json');rows=campaign.scenarios(c)
        assert len(rows)==count and all(ssstateen.reference(r)['status']=='pass' for r in rows)
        for row in rows:
            assert all(f'csrw {0x30c+i:#x}' not in row['assembly'] for i in range(4))
            assert row['reference_mode']=='model-observations'
        machine=next(r for r in rows if r['id']=='ssstateen-stateen-0-m-00')
        assert ssstateen.reference(machine)['actual']==dict(denied=False,cause=11)
        supervisor=next(r for r in rows if r['id']=='ssstateen-stateen-0-s-00')
        assert ssstateen.reference(supervisor)['actual']==dict(denied=False,cause=9)
        if name.endswith('-h'):
            guest=next(r for r in rows if r['id']=='ssstateen-zfinx-0-vu-10')
            assert ssstateen.reference(guest)['actual']==dict(denied=True,cause=22)
            changed=deepcopy(guest);changed['reference_model']['cause']=2
            assert ssstateen.reference(changed)['status']=='fail'


def test_machine_bank_and_missing_writable_gates_rejected():
    c=campaign.load('examples/privilege/ssstateen-only-h.json');c['isa']+='_smstateen'
    with pytest.raises(ValueError,match='without Smstateen'):campaign.scenarios(c)
    c=campaign.load('examples/privilege/ssstateen-only-h.json');c['stateen']['writable_bits']=[1]
    with pytest.raises(ValueError,match='writable'):campaign.scenarios(c)
