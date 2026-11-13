"""Campaign controls, build failures, resume identity and denominator rules."""
import json
import sys
import pytest
from rvw.cov.core_mutation import prepare,run_campaign,classify,candidates,tables,KILLS

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('receipt,rc,expected',[
    ({},1,'invalid'),
    ({'schema':'rvw.mutation-test/1','outcome':'FAIL'},1,'invalid'),
    ({'schema':'rvw.mutation-test/1','outcome':KILLS[0]},1,'invalid'),
    *[({'schema':'rvw.mutation-test/1','outcome':k,'evidence':{'line':1}},1,k) for k in KILLS],
    ({'schema':'rvw.mutation-test/1','outcome':'pass'},0,'invalid'),
    ({'schema':'rvw.mutation-test/1','outcome':'pass','strict_spike_match':True},0,'pass'),
    ({'schema':'rvw.mutation-test/1','outcome':'pass','strict_spike_match':True},1,'invalid'),
])
def test_explicit_evidence(receipt,rc,expected):
    assert classify(receipt,rc)==expected


def test_scope_and_comments():
    text='module a;\n// x + y\nassign x = a + b;\nendmodule\nmodule b;\nassign x = a - b;\nendmodule\n'
    rows=candidates(text,[dict(id='alu',module='b',pattern='assign')],60)
    assert len(rows)==1 and rows[0]['line']==6
    assert rows[0]['new']=='assign x = a + b;\n'


@pytest.fixture
def campaign(tmp_path):
    (tmp_path/'design.v').write_text('module dut;\nassign q = a + b;\nassign r = a & b;\nendmodule\n')
    (tmp_path/'test.elf').write_text('fixture, not native evidence')
    driver=tmp_path/'driver.py'
    driver.write_text('''import sys,json,pathlib
mode,rtl,build=sys.argv[1:4]
p=pathlib.Path(build);p.mkdir(exist_ok=True)
if mode=='build':
 with (p.parent/'build-count').open('a') as f:f.write('build\\n')
 if 'a - b' in pathlib.Path(rtl).read_text():sys.exit(1)
else:
 receipt,test,identity=sys.argv[4:7]
 changed='a | b' in pathlib.Path(rtl).read_text()
 pathlib.Path(receipt).write_text(json.dumps(dict(schema='rvw.mutation-test/1',
  outcome='killed by self-check' if changed else 'pass',evidence={'tohost':3},
  strict_spike_match=not changed,rtl_sha256=identity,test=test)))
''')
    manifest=tmp_path/'project.json'
    manifest.write_text(json.dumps(dict(schema='rvw.core-mutation-project/1',rtl='design.v',
        inputs=['driver.py','test.elf'],scopes=[dict(id='alu',module='dut',pattern='assign')],
        tests=[dict(id='add',source='riscv-tests',tier='a',elf='test.elf')],
        build=[sys.executable,str(driver),'build','{rtl}','{build}'],
        test=[sys.executable,str(driver),'test','{rtl}','{build}','{receipt}','{test}','{rtl_sha256}'],
        equivalence=[sys.executable,'-c','pass'])))
    out=tmp_path/'run';prepare(manifest,out)
    return out


def test_build_failure_not_kill_and_build_once(campaign):
    data=run_campaign(campaign)
    assert data['baseline']['state']=='survived'
    assert [r['state'] for r in data['mutants']]==['invalid','killed by self-check']
    assert data['mutants'][0]['tests']==[]
    assert len((campaign/'build-count').read_text().splitlines())==3
    assert not (campaign/'build').exists()
    assert data['tables']['modules']['alu']['kill_rate']==1
    run_campaign(campaign,resume=True)
    assert len((campaign/'build-count').read_text().splitlines())==3


def test_resume_refuses_changed_inputs(campaign):
    run_campaign(campaign)
    (campaign.parent/'test.elf').write_text('changed')
    with pytest.raises(ValueError,match='input changed'):run_campaign(campaign,resume=True)


def test_empty_denominator():
    data=tables([dict(scope='x',state='invalid',tests=[])])
    assert data['modules']['x']['kill_rate'] is None


def test_failed_control_stops(campaign):
    plan=json.loads((campaign/'plan.json').read_text())
    plan['project']['build']=[sys.executable,'-c','raise SystemExit(1)']
    (campaign/'plan.json').write_text(json.dumps(plan))
    data=run_campaign(campaign)
    assert data['status']=='inconclusive' and data['mutants']==[]


def test_no_equivalence_claim_without_proof(campaign):
    # Select a candidate that this fixture does not detect. No proof result exists.
    plan=json.loads((campaign/'plan.json').read_text())
    row=plan['mutants'][1];row['new']=row['old'].replace('a & b','b & a')
    plan['mutants']=[row]
    (campaign/'plan.json').write_text(json.dumps(plan))
    data=run_campaign(campaign)
    assert data['mutants'][0]['state']=='survived'
    assert not data['mutants'][0]['test_gap']


def test_timeout_is_not_detection(campaign,monkeypatch):
    from rvw.cov import core_mutation as module
    from rvw.common.proc import Result
    monkeypatch.setattr(module,'_command',lambda *args:Result(124,True))
    data=run_campaign(campaign)
    assert data['baseline']['state']=='timeout'
    assert data['status']=='inconclusive'
    assert all(n==0 for n in data['counts'].values())


@pytest.mark.parametrize('verdict,expected,gap',[
    ('equivalent','equivalent (proved)',False),
    ('not_equivalent','survived',True),
    ('bounded_match','survived',False),
    ('inconclusive','survived',False),
])
def test_formal_evidence(campaign,monkeypatch,verdict,expected,gap):
    from rvw.cov import core_mutation as module
    from rvw.common.proc import Result
    plan=json.loads((campaign/'plan.json').read_text())
    row=plan['mutants'][1];row['new']=row['old'].replace('a & b','b & a')
    plan['mutants']=[row];(campaign/'plan.json').write_text(json.dumps(plan))
    original=module._command
    def command(argv,values,root,log,deadline):
        if log.name!='equivalence.log':return original(argv,values,root,log,deadline)
        proof=campaign/row['id']/'equivalence';proof.mkdir()
        (proof/'result.json').write_text(json.dumps(dict(schema='rvw.formal.equiv/1',status=verdict)))
        return Result(0 if verdict=='equivalent' else 1)
    monkeypatch.setattr(module,'_command',command)
    result=run_campaign(campaign)['mutants'][0]
    assert result['state']==expected and result['test_gap']==gap


@pytest.mark.parametrize('evidence,before,unknown',[
    ({'detection_cycle':5,'reference_mismatch_cycle':9},1,0),
    ({'detection_cycle':5},0,1),
    ({'detection_cycle':5,'reference_mismatch_cycle':5},0,1),
])
def test_no_inferred_early_detection(evidence,before,unknown):
    row=dict(scope='rob',state=KILLS[2],tests=[dict(source='checks',outcome=KILLS[2],
        receipt=dict(evidence=evidence))])
    result=tables([row])['timing']
    assert result['property_before_reference']==before
    assert result['property_timing_unmeasured']==unknown
