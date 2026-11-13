import copy
import pytest
from rvw.cov.guidance import Guide
from rvw.cov.rtl import identity


def settings():
    plan = {'schema':'rvw.rtl-plan/1','design':'a'*64,
            'clock':{'signal':'TOP.c','edge':'rising','sampling':'pre-edge'},
            'reset':{'signal':'TOP.r','active':1,'rule':'disable-clear'},
            'signals':{s:{'width':1,'type':'Bool','scala':None} for s in ('TOP.c','TOP.r','TOP.x')},
            'bins':[{'id':v,'kind':'event','domain':'speculative','when':{'TOP.x':[i]}} for i,v in enumerate(('zero','one'))]}
    recipes = {'schema':'rvw.event-recipes/1','plan_id':identity(plan),'design':plan['design'],
               'recipes':[{'goal':'a','targets':['zero']},{'goal':'b','targets':['one']}]}
    report = {'schema':'rvw.rtl-coverage/1','design':plan['design'],'plan_id':identity(plan),
              'status':'ok','sampling_complete':True,'bins':[{'id':'zero','count':1},{'id':'one','count':0}],
              'inputs':[{'sha256':'b'*64}]}
    return plan, recipes, report


def test_measured_event_changes_selection_and_replay():
    plan, recipes, report = settings()
    guide = Guide(plan, recipes)
    assert guide.choose(['a','b']) == 'a'
    feedback = guide.observe('a',report,qualified=True,rtl_sha256=plan['design'])
    assert feedback['new_events'] == ['zero']
    assert guide.choose(['a','b']) == 'b'
    assert Guide(plan,recipes,guide.history).choose(['a','b']) == 'b'
    with pytest.raises(ValueError,match='repeated'):
        guide.observe('b',report,qualified=True,rtl_sha256=plan['design'])


def test_unmapped_targets_and_uncompleted_sequences_remain_holes():
    plan,recipes,report=settings()
    plan['sequences']=[{'id':'pair','domain':'speculative','steps':[
        {'when':{'TOP.x':[0]}},{'when':{'TOP.x':[1]},'delay':[1,2]}]}]
    recipes['plan_id']=identity(plan);report['plan_id']=identity(plan)
    report['sequences']=[{'id':'pair','completed':0,'pending':2}]
    guide=Guide(plan,recipes)
    guide.observe('a',report,qualified=True,rtl_sha256=plan['design'])
    summary=guide.coverage_summary({'a'})
    assert summary['declared_bins']==summary['full_input_bins']==3
    assert summary['observed']==['zero'] and summary['unobserved']==['one','pair']
    assert summary['uncompleted_sequences']==['pair']
    assert summary['last_sample_pending']=={'pair':2}
    assert summary['unsupported_targets']==['one','pair']


@pytest.mark.parametrize('field,value', [('sampling_complete',False),('status','inconclusive'),('design','wrong'),('plan_id','wrong')])
def test_stale_or_incomplete_samples_cannot_reward(field,value):
    plan, recipes, report = settings()
    guide = Guide(plan,recipes)
    report[field] = value
    with pytest.raises(ValueError,match='incompatible'):
        guide.observe('a',report,qualified=True,rtl_sha256=plan['design'])
    assert guide.history == []


def test_unqualified_execution_and_wrong_recipe_refuse():
    plan,recipes,report = settings()
    guide = Guide(plan,recipes)
    with pytest.raises(ValueError,match='qualified execution'):
        guide.observe('a',report,qualified=False,rtl_sha256=plan['design'])
    recipes['recipes'][0]['targets'] = ['unknown']
    with pytest.raises(ValueError,match='declared RTL targets'):
        Guide(plan,recipes)


def test_missing_core_hook_is_unsupported_and_charged(tmp_path,monkeypatch):
    from rvw.cov import feedback_campaign as f
    from types import SimpleNamespace
    plan,recipes,_=settings()
    guide=Guide(plan,recipes)
    result=tmp_path/'run/result.json';result.parent.mkdir();result.write_text('{}')
    elf=tmp_path/'program.elf';elf.write_bytes(b'elf')
    run=SimpleNamespace(elf_sha256=f.digest(elf),why_inconclusive=None,status='pass',artifact=lambda _:None)
    monkeypatch.setattr(f,'load_run',lambda _:run)
    outcome=f.collect(guide,'a',elf,result.parent,'plan',True)
    assert outcome['status']=='unsupported' and outcome['new_events']==[]
    assert guide.choose(['a','b'])=='b'
    assert len(guide.history)==1


def test_stale_sample_receipt_cannot_reward(tmp_path,monkeypatch):
    from rvw.cov import feedback_campaign as f
    from types import SimpleNamespace
    plan,recipes,_=settings();guide=Guide(plan,recipes)
    result=tmp_path/'run/result.json';result.parent.mkdir();result.write_text('{}')
    elf=tmp_path/'program.elf';elf.write_bytes(b'elf')
    trace=tmp_path/'rvfi.jsonl';trace.write_text('trace')
    samples=tmp_path/'samples.jsonl';samples.write_text('samples')
    receipt={'elf_sha256':'stale','rvfi_sha256':f.digest(trace),'samples_sha256':f.digest(samples),
             'plan_id':guide.plan_id,'rtl_sha256':guide.design}
    run=SimpleNamespace(elf_sha256=f.digest(elf),why_inconclusive=None,status='pass',path=result.parent,
        artifact=lambda key:{'rtl_samples':samples,'rvfi_trace':trace}.get(key),
        extra={'rtl_sha256':guide.design,'details':{'rtl_samples':receipt}})
    monkeypatch.setattr(f,'load_run',lambda _:run)
    outcome=f.collect(guide,'a',elf,result.parent,'plan',True)
    assert outcome['status']=='unsupported' and outcome['new_events']==[]
    assert 'receipt' in outcome['reason']


def test_exact_receipt_uses_real_sampler(tmp_path,monkeypatch):
    import json
    from rvw.cov import feedback_campaign as f
    from types import SimpleNamespace
    plan,recipes,_=settings();guide=Guide(plan,recipes)
    config=tmp_path/'plan.json';config.write_text(json.dumps(plan))
    result=tmp_path/'run/result.json';result.parent.mkdir();result.write_text('{}')
    elf=tmp_path/'program.elf';elf.write_bytes(b'elf')
    trace=tmp_path/'rvfi.jsonl';trace.write_text('trace')
    samples=tmp_path/'samples.jsonl'
    rows=[{'schema':'rvw.rtl-samples/1','plan_id':identity(plan),'design':plan['design']},
          {'cycle':0,'values':{'TOP.c':0,'TOP.r':0,'TOP.x':0}},
          {'event':'end','complete':True}]
    samples.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    receipt={'elf_sha256':f.digest(elf),'rvfi_sha256':f.digest(trace),'samples_sha256':f.digest(samples),
             'plan_id':guide.plan_id,'rtl_sha256':guide.design}
    run=SimpleNamespace(elf_sha256=f.digest(elf),why_inconclusive=None,status='pass',path=result.parent,
        artifact=lambda key:{'rtl_samples':samples,'rvfi_trace':trace}.get(key),
        extra={'rtl_sha256':guide.design,'details':{'rtl_samples':receipt}})
    monkeypatch.setattr(f,'load_run',lambda _:run)
    outcome=f.collect(guide,'a',elf,result.parent,config,True)
    assert outcome['status']=='observed' and outcome['new_events']==['zero']
    assert outcome['report']['denominator']==2
