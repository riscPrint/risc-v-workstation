"""Plan closure must retain missing probe goals and refuse weak reference evidence."""
import json
import pytest
from rvw.plan.model import VPlan
pytestmark=pytest.mark.fast


def setup(tmp_path):
    report={'schema':'rvw.probe-coverage/1','status':'qualified','plan_id':'plan','design':'rtl',
        'comparison':{'status':'match','instructions':4,'trace_complete':True,'synchronized':0,'applied_masks':[]},
        'bins':[{'id':'event','count':1}], 'sequences':[{'id':'sequence','completed':0,'pending':1}]}
    evidence=tmp_path/'probe.json';evidence.write_text(json.dumps(report))
    plan=tmp_path/'plan.json';plan.write_text(json.dumps({'schema':'rvw.vplan/1','requirements':{'R':'Observe both goals.'},
        'features':[{'id':'events','requirements':['R'],'coverage':[{'path':'probe.json','groups':['event','sequence']}]}]}))
    return plan,evidence,report


def test_pending_sequence_remains_open(tmp_path):
    plan,_,_=setup(tmp_path)
    row=VPlan(plan).status()['features'][0]
    assert row['status']=='open' and row['coverage_hit']==1 and row['coverage_expected']==2
    assert row['holes'][0]['group']=='sequence'


@pytest.mark.parametrize('field,value',[('status','mismatch'),('trace_complete',False),('instructions',0),('synchronized',1),('applied_masks',['mask'])])
def test_weak_reference_evidence_cannot_close_plan(tmp_path,field,value):
    plan,evidence,report=setup(tmp_path);report['comparison'][field]=value;evidence.write_text(json.dumps(report))
    row=VPlan(plan).status()['features'][0]
    assert row['status']=='open'
    assert 'qualification' in row['holes'][0]['reason']
