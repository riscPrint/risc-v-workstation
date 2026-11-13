import copy
import json
import pytest
from rvw.farm.gate_intake import intake
from rvw.results import SuiteResults, TestEntry, save_results

pytestmark=pytest.mark.fast


def fixture(tmp_path):
    source=dict(core_dirty=False,tools_dirty=False,core_rev_full='a'*40,tools_rev='c'*40,core_repo='/work/core',tools_repo='/work/tools')
    tools={'native_build':{'cache_enabled':True,'sha256':'d'*64}}
    root=tmp_path/'evidence';cell=root/'cell';cell.mkdir(parents=True)
    run=dict(schema='rvw.run/1',status='pass',core='generic',config='small',seed=1,elf_sha256='b'*64,rtl_sha256='e'*64,source=source,tools=tools)
    (cell/'result.json').write_text(json.dumps(run))
    result=SuiteResults('run','isa','generic','small','2026-11-13',source=copy.deepcopy(source),tests=[TestEntry('test','pass',seed=1,run='cell',extra={'elf_sha256':'b'*64,'rtl_sha256':'e'*64,'tools':copy.deepcopy(tools),'kind':'elf-dir','options':{'max_cycles':None,'mem_latency':None}})])
    save_results(result,root)
    return root,cell,run,result


def test_native_intake_binds_recorded_full_identities(tmp_path):
    root,_,_,_=fixture(tmp_path)
    result=intake(root)
    assert result['tests']==1
    assert result['cells'][0]['core_revision']=='a'*40
    assert result['cells'][0]['harness_revision']=='c'*40
    assert result['cells'][0]['native_build_sha256']=='d'*64


@pytest.mark.parametrize('change',['dirty','build','outcome','source','incomplete'])
def test_native_intake_refuses_unearned_gate_evidence(tmp_path,change):
    root,cell,run,result=fixture(tmp_path)
    if change=='dirty':run['source']['tools_dirty']=True
    elif change=='build':run['tools']['native_build']['cache_enabled']=False
    elif change=='outcome':run['status']='fail';run['fail_code']=2
    elif change=='source':result.source['core_rev_full']='f'*40
    else:result.source['identity_complete']=False
    (cell/'result.json').write_text(json.dumps(run));save_results(result,root)
    with pytest.raises(ValueError):intake(root)
    assert not (root/'verdict.json').exists()


def test_empty_native_gate_has_no_checks(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(ValueError,match='no C3'):
        intake(tmp_path)


def test_regress_gate_structured_api_honors_verdict_destination(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from rvw.regress import cli
    from rvw.results import Verdict
    seen={}
    monkeypatch.setattr(cli,'load_config',lambda *args,**kwargs:SimpleNamespace(known_failures=None))
    def fake_gate(*args,**kwargs):
        seen.update(kwargs)
        return {'verdict':Verdict('accept',tests='pass'),'file':kwargs['out']}
    monkeypatch.setattr(cli,'gate',fake_gate)
    result=cli.execute_json('gate',base='base',cand='candidate',out=str(tmp_path/'verdict.json'))
    assert result['verdict']=='accept'
    assert seen['out']==tmp_path/'verdict.json'


def test_requested_trace_must_exist_even_when_native_options_claim_it(tmp_path):
    root,cell,run,result=fixture(tmp_path)
    run['options']={'rvfi_trace':True}
    result.tests[0].extra['options']['rvfi_trace']=True
    (cell/'result.json').write_text(json.dumps(run));save_results(result,root)
    with pytest.raises(ValueError,match='trace is missing'):
        intake(root)


def test_queue_and_live_view_keep_recorded_reject_separate_from_completion(tmp_path):
    import sys
    from rvw.farm.service import Queue
    from rvw.farm.live import snapshot
    queue=Queue(tmp_path)
    queue.submit('alice',[sys.executable,'-c',"import json;from pathlib import Path;Path('verdict.json').write_text(json.dumps(dict(schema='rvw.verdict/2',verdict='reject',tests='fail')))"])
    job=queue.work_once()
    assert job['state']=='complete'
    assert job['attempts'][0]['gate_verdict']=='reject'
    assert len(job['attempts'][0]['gate_sha256'])==64
    view=snapshot(queue,'alice')
    assert view['runs'][0]['recorded_gate']=='reject'
    assert view['runs'][0]['passes']==0
    assert view['gate_acceptance']=='not_inferred'
