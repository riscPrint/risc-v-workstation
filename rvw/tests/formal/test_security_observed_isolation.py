"""Closed-core isolation observes outputs without turning them into free inputs."""
import copy
import json
from pathlib import Path
import runpy
import pytest
from rvw.formal.security.policy import isolation

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[3]
expose=runpy.run_path(str(ROOT/'examples/vexriscv/formal/pmp-isolation.py'))['expose']


def data():
    p=json.loads((ROOT/'examples/vexriscv/formal/pmp-isolation-policy.json').read_text())
    widths={'request':1,'grant':1,'address':32,'write':1,'execute':1,'privilege':2,'master':1}
    ports={'clk':{'direction':'input','bits':[1]},'reset':{'direction':'input','bits':[2]}}
    bit=3
    for role,name in p['signals'].items():
        ports[name]={'direction':'output','bits':list(range(bit,bit+widths[role]))};bit+=widths[role]
    return {'modules':{'Core':{'ports':ports}}},p


def test_observed_mode_accepts_only_output_access_roles():
    d,p=data()
    text=isolation(d,'Core',p)
    assert '.obs_address(obs_address)' in text
    assert 'output [31:0] obs_address' in text
    q=copy.deepcopy(p);q.pop('observed_access')
    with pytest.raises(ValueError,match='access signals'):isolation(d,'Core',q)
    d['modules']['Core']['ports']['obs_address']['direction']='input'
    with pytest.raises(ValueError,match='observed_access'):isolation(d,'Core',p)


def test_project_exposure_adds_no_free_inputs_or_state_cuts():
    mod={'ports':{'clk':{'direction':'input','bits':[1]}},'netnames':{'bus':{'bits':[2]}},
         'cells':{'ff':{'type':'$dff','connections':{'Q':[2],'D':[3],'CLK':[1]}}}}
    design={'modules':{'Core':mod}}
    binding={'source_top':'Core','observation_top':'Observed','signals':{'obs':'bus'},'constants':{'master':[1,0]}}
    result=expose(design,binding)['modules']['Observed']
    assert result['cells']==mod['cells']
    assert {n:p for n,p in result['ports'].items() if p['direction']=='input'}==mod['ports']
    assert result['ports']['obs']['bits']==[2]
    assert design['modules']['Core']==mod and 'obs' not in mod['ports']
    binding['signals']['obs']='missing'
    with pytest.raises(ValueError):expose(design,binding)
