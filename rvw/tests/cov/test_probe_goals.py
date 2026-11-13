"""Probe goals retain timing holes and reject incomplete reference execution."""
import json,importlib
from types import SimpleNamespace
import pytest
m=importlib.import_module('rvw.cov.probe_goals')
pytestmark=pytest.mark.fast


def setup(tmp_path,monkeypatch):
    elf=tmp_path/'program';elf.write_bytes(b'elf')
    trace=tmp_path/'trace';trace.write_text('{}')
    events=tmp_path/'events'
    ident={'core':'test','config':'test','seed':1,'elf_sha256':m.digest(elf),'rtl_sha256':'rtl'}
    rows=[{'schema':'rvw.probe-events/1','identity':ident,'probes':[
        {'id':0,'kind':'custom','name':'request','fields':[['v',1]]},
        {'id':1,'kind':'custom','name':'response','fields':[['v',1]]}]},[1,0,1],[3,1,1],
        {'end':True,'cycles':10,'events':{'0':1,'1':1}}]
    events.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    result=tmp_path/'result';result.write_text('{}')
    run=SimpleNamespace(why_inconclusive=None,status='pass',core='test',config='test',seed=1,
        elf_sha256=m.digest(elf),extra={'rtl_sha256':'rtl'},elf=elf,path=tmp_path,instret=4,cycles=10,
        artifact={'probe_events':events,'rvfi_trace':trace}.get)
    monkeypatch.setattr(m,'load_run',lambda _:run)
    monkeypatch.setattr(m,'cosim',lambda *a,**kw:{'status':'match','instructions':4,'trace_complete':True,
        'end_status':'pass','synchronized':0,'applied_masks':[]})
    plan=tmp_path/'plan';plan.write_text(json.dumps({'schema':'rvw.probe-goals/1','design':'rtl','bins':[
        {'id':'req','kind':'custom','name':'request','fields':{'v':[1]}},
        {'id':'resp','kind':'custom','name':'response','fields':{'v':[1]}}],
        'sequences':[{'id':'req-resp','steps':['req','resp'],'max_gap':2}]}))
    return result,plan,trace,events


def test_timed_sequence_and_expired_pending(tmp_path,monkeypatch):
    result,plan,*_=setup(tmp_path,monkeypatch)
    r=m.probe_goals(result,plan,'platform')
    assert r['holes']==[]
    assert r['sequences']==[{'id':'req-resp','completed':1,'pending':0}]
    d=json.loads(plan.read_text());d['sequences'][0]['max_gap']=1;plan.write_text(json.dumps(d))
    assert m.probe_goals(result,plan,'platform')['holes']==['req-resp']


def test_incomplete_probe_stream_earns_no_coverage(tmp_path,monkeypatch):
    result,plan,trace,events=setup(tmp_path,monkeypatch)
    events.write_text('\n'.join(events.read_text().splitlines()[:-1])+'\n')
    with pytest.raises(ValueError,match='incomplete'):m.probe_goals(result,plan,'platform')


def test_synchronized_comparison_earns_no_coverage(tmp_path,monkeypatch):
    result,plan,*_=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(m,'cosim',lambda *a,**kw:{'status':'match','instructions':4,'trace_complete':True,
        'end_status':'pass','synchronized':1,'applied_masks':[]})
    with pytest.raises(ValueError,match='strict Spike'):m.probe_goals(result,plan,'platform')


@pytest.mark.parametrize('damage',['identity','accounting','width'])
def test_bad_probe_evidence_cannot_earn_hits(tmp_path,monkeypatch,damage):
    result,plan,trace,events=setup(tmp_path,monkeypatch)
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    if damage=='identity':rows[0]['identity']['elf_sha256']='other'
    if damage=='accounting':rows[-1]['events']['0']=2
    if damage=='width':rows[1][-1]=2
    events.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError):m.probe_goals(result,plan,'platform')


def test_same_cycle_steps_do_not_complete_sequence(tmp_path,monkeypatch):
    result,plan,trace,events=setup(tmp_path,monkeypatch)
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    rows[2][0]=1
    events.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert m.probe_goals(result,plan,'platform')['holes']==['req-resp']


def test_probe_feedback_uses_ucb_and_refuses_reused_stream(tmp_path,monkeypatch):
    from rvw.cov.guidance import Guide
    from rvw.cov.rtl import identity
    result,plan,*_=setup(tmp_path,monkeypatch)
    data=json.loads(plan.read_text());data['sequences'][0]['max_gap']=1;plan.write_text(json.dumps(data))
    recipes={'schema':'rvw.event-recipes/1','plan_id':identity(data),'design':'rtl','recipes':[
        {'goal':'first','targets':['req']},{'goal':'second','targets':['req-resp']}]}
    guide=Guide(data,recipes)
    report=m.probe_goals(result,plan,'platform')
    assert guide.choose(['first','second'])=='first'
    feedback=guide.observe('first',report,qualified=True,rtl_sha256='rtl')
    assert feedback['new_events']==['req','resp']
    assert guide.choose(['first','second'])=='second'
    with pytest.raises(ValueError,match='repeated'):
        guide.observe('second',report,qualified=True,rtl_sha256='rtl')


def test_campaign_captures_probe_and_coverage_model_options():
    from rvw.cov.campaign import execution_options
    assert execution_options({})=={}
    assert execution_options({'probe_plan':'plan','coverage':True})=={'coverage':True,'probes':True}
