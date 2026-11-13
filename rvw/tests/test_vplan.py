"""Project mapping fixtures. These do not establish native verification closure."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from rvw.plan import VPlan
from rvw.plan.cli import execute_json


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data));return path


def setup(tmp_path):
    write(tmp_path/'coverage.json',{'schema':'rvw.functional-coverage/1','config_sha256':'a'*64,
        'qualification_policy':'c1-pass-complete-c2-v1',
        'groups':{'operands':{'fields':['value'],'expected_bins':2,'expected_hit':1,'holes':[['one']]}}})
    write(tmp_path/'c1.json',{'schema':'rvw.run/1','status':'pass'})
    data={'schema':'rvw.vplan/1','requirements':{'REQ.ADD':'Add produces the required result.','REQ.OTHER':'Another obligation.'},
          'features':[{'id':'add','requirements':['REQ.ADD'],'coverage':[{'path':'coverage.json','groups':['operands']}],
                       'tests':[{'path':'c1.json'}]}]}
    return write(tmp_path/'plan.json',data)


def test_rollup_keeps_holes_and_unassigned_requirements(tmp_path):
    path=setup(tmp_path);result=VPlan(path).status()
    assert result['summary']['open']==1 and result['summary']['holes']==1
    assert result['unassigned_requirements']==['REQ.OTHER']
    assert result['features'][0]['coverage_expected']==2 and result['features'][0]['coverage_hit']==1
    assert result['features'][0]['evidence'][1]['status']=='recorded_pass'


def test_trend_uses_same_plan_and_compatible_context(tmp_path):
    path=setup(tmp_path);before=VPlan(path).status();previous=write(tmp_path/'before.json',before)
    coverage=json.loads((tmp_path/'coverage.json').read_text())
    coverage['groups']['operands'].update(expected_hit=2,holes=[]);write(tmp_path/'coverage.json',coverage)
    after=VPlan(path).status(previous)
    feature=after['features'][0]
    assert feature['status']=='reported_closed'
    assert feature['trend']=={'status':'comparable','hole_delta':-1,'coverage_hit_delta':1}
    coverage['config_sha256']='b'*64;write(tmp_path/'coverage.json',coverage)
    assert VPlan(path).status(previous)['features'][0]['trend']['status']=='incompatible_coverage_context'
    data=json.loads(path.read_text());data['requirements']['REQ.ADD']='Changed requirement.';write(path,data)
    with pytest.raises(ValueError,match='same verification plan'): VPlan(path).status(previous)


def test_failed_and_stale_evidence_stays_open(tmp_path):
    path=setup(tmp_path);write(tmp_path/'c1.json',{'schema':'rvw.run/1','status':'pass','inconclusive':'unknown inputs'})
    data=json.loads(path.read_text());data['features'][0]['coverage'][0]['sha256']='wrong';write(path,data)
    result=VPlan(path).status()
    assert result['features'][0]['hole_count']==2
    assert result['summary']['reported_closed']==0


def test_no_checks_and_missing_groups_remain_holes(tmp_path):
    path=setup(tmp_path);data=json.loads(path.read_text())
    data['features'].append({'id':'empty','requirements':['REQ.OTHER']})
    data['features'][0]['coverage'][0]['groups']=['missing'];write(path,data)
    result=VPlan(path).status()
    assert result['summary']['open']==2
    assert any('no evidence' in h['reason'] for h in result['features'][1]['holes'])


def test_bounded_formal_cannot_close_unbounded_obligation(tmp_path):
    path=setup(tmp_path);data=json.loads(path.read_text())
    data['features'][0]['coverage']=[];data['features'][0]['formal']=[{'path':'formal/result.json','properties':['p']}];write(path,data)
    write(tmp_path/'formal/result.json',{'schema':'rvw.formal-app-results/1','properties':[
        {'property_id':'p','status':'pass','proof_kind':'bounded','result':'p/result.json'}]})
    child={'schema':'rvw.formal/1','status':'pass','proof_kind':'bounded','assertions':1,'reachability':{'status':'reachable'}}
    write(tmp_path/'formal/p/result.json',child)
    assert VPlan(path).status()['features'][0]['status']=='open'
    child['proof_kind']='unbounded';write(tmp_path/'formal/p/result.json',child)
    summary=json.loads((tmp_path/'formal/result.json').read_text());summary['properties'][0]['proof_kind']='unbounded'
    write(tmp_path/'formal/result.json',summary)
    result=VPlan(path).status()
    assert result['features'][0]['status']=='reported_closed'
    child['reachability']=None;write(tmp_path/'formal/p/result.json',child)
    assert VPlan(path).status()['features'][0]['status']=='open'


def test_cli_mcp_api_parity(tmp_path):
    path=setup(tmp_path)
    ran=subprocess.run([sys.executable,'-m','rvw','plan','status',str(path),'--json'],capture_output=True,text=True)
    cli=json.loads(ran.stdout);api=execute_json(plan=path)
    assert ran.returncode=={'pass':0,'fail':1}.get(cli['verdict'],3),ran.stderr
    assert cli['summary']==api['summary'] and cli['features']==api['features']


def test_block_only_evidence_cannot_close_new_integration_wiring(tmp_path):
    path=setup(tmp_path);data=json.loads(path.read_text())
    data['features'][0]={'id':'block','requirements':['REQ.ADD'],'checks':[{'kind':'block','path':'reuse.json'}]}
    write(path,data);write(tmp_path/'reuse.json',{'schema':'rvw.block-reuse/1','status':'eligible_for_reuse',
                                              'holes':[],'new_wiring_covered':False})
    assert VPlan(path).status()['features'][0]['status']=='open'
    data['features'][0]['scope']='block';write(path,data)
    assert VPlan(path).status()['features'][0]['status']=='reported_closed'


def test_rtl_sequences_and_gate_failure_are_separate_holes(tmp_path):
    path=setup(tmp_path);data=json.loads(path.read_text())
    data['features'][0]['coverage']=[{'path':'rtl.json','groups':['event','sequence']}]
    data['features'][0]['checks']=[{'path':'verdict.json','kind':'gate'}];write(path,data)
    write(tmp_path/'rtl.json',{'schema':'rvw.rtl-coverage/1','status':'ok','sampling_complete':True,
        'plan_id':'p','design':'d','bins':[{'id':'event','count':1}],
        'sequences':[{'id':'sequence','completed':0,'pending':2}]})
    write(tmp_path/'verdict.json',{'schema':'rvw.verdict/2','verdict':'inconclusive','tests':'incomplete'})
    result=VPlan(path).status()['features'][0]
    assert result['coverage_expected']==2 and result['coverage_hit']==1
    assert result['hole_count']==2 and result['status']=='open'


def test_suite_selection_keeps_missing_and_inconclusive_tests_open(tmp_path):
    path=setup(tmp_path);data=json.loads(path.read_text())
    data['features'][0]['coverage']=[];data['features'][0]['tests']=[{'path':'suite.json','ids':['test']}];write(path,data)
    suite={'schema':'rvw.results/1','run_id':'fixture','suite':'fixture','core':'fixture','config':'fixture','created':'fixture',
           'tests':[{'id':'test','status':'pass'}]}
    write(tmp_path/'suite.json',suite)
    assert VPlan(path).status()['features'][0]['status']=='reported_closed'
    suite['tests'][0]['inconclusive']='unattributed';write(tmp_path/'suite.json',suite)
    assert VPlan(path).status()['features'][0]['status']=='open'
    suite['tests']=[];write(tmp_path/'suite.json',suite)
    assert VPlan(path).status()['features'][0]['status']=='open'


def test_cli_exit_code_carries_rolled_up_verdict(tmp_path):
    plan=write(tmp_path/'p.json',{'schema':'rvw.vplan/1','requirements':{'R':'x'},
        'features':[{'id':'f','requirements':['R'],'tests':[{'path':'c1.json'}]}]})
    for status,verdict,code in (('fail','fail',1),('pass','pass',0)):
        write(tmp_path/'c1.json',{'schema':'rvw.run/1','status':status})
        ran=subprocess.run([sys.executable,'-m','rvw','plan','status',str(plan),'--json'],capture_output=True,text=True)
        assert json.loads(ran.stdout)['verdict']==verdict and ran.returncode==code,ran.stdout
    write(tmp_path/'c1.json',{'schema':'rvw.run/1','status':'error'})
    ran=subprocess.run([sys.executable,'-m','rvw','plan','status',str(plan)],capture_output=True,text=True)
    assert ran.returncode==3 and 'Verdict: ' in ran.stdout
