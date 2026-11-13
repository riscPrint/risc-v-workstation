import json
import pytest
from rvw.arch.energy import energy

pytestmark=pytest.mark.fast


def test_workload_state_and_event_energy(tmp_path):
    (tmp_path/'run').write_text(json.dumps(dict(schema='rvw.ooo-run/1',cycles=100,events={'issued':50})))
    p=tmp_path/'plan';spec=dict(schema='rvw.system-energy-plan/1',run='run',clock_ghz=2,
            components={'cpu':dict(kind='cpu',source='assumed example coefficients',
                state_cycles={'active':80,'idle':20},state_mw={'active':10,'idle':2},
                event_pj={'issued':2},transitions=[{'from':'active','to':'idle','count':1,'energy_pj':5}])})
    p.write_text(json.dumps(spec));r=energy(p,tmp_path/'out')
    assert r['total_energy_pj']==525
    assert r['average_power_mw']==10.5
    assert r['calibration_status']=='not_performed'
    spec['components']['cpu']['state_cycles']['idle']=10;p.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='partition'):energy(p,tmp_path/'bad')
