import json
from types import SimpleNamespace
import pytest
from rvw.privilege import campaign
from rvw.privilege.events import MailboxDriver
from rvw.privilege.reset_phase import PhaseDriver,observe,programs

pytestmark=pytest.mark.fast


def event(step=1):
    return dict(step=step,kind='reset',prepare=[{'action':'hold_response'}],cleanup=[{'action':'release_response'}],
                phase_gate={'outstanding':{'mask':3,'value':1}},min_wait_ticks=2)


def test_preparation_precedes_observed_phase_and_cleanup_precedes_ack():
    e=event();d=PhaseDriver([e]);log=[];state={'outstanding':1}
    def drive(action):
        log.append(action['kind'])
        if action['kind']=='reset':state['outstanding']=0
    assert not d.service(0,drive,log.append,tick=0,state=state)
    assert not d.service(1,drive,log.append,tick=1,state=state)
    assert not d.service(1,drive,log.append,tick=2,state=state)
    assert not d.service(1,drive,log.append,tick=3,state={'outstanding':0})
    assert d.service(1,drive,log.append,tick=4,state=state)
    assert log==['reset-prepare','reset','reset-cleanup',1]
    assert d.complete and d.receipts[0]['state']=={'outstanding':1}
    assert observe([e],d.receipts)['status']=='pass'


def test_failed_reset_releases_hold_without_ack():
    d=PhaseDriver([event()]);log=[]
    def drive(action):
        log.append(action['kind'])
        if action['kind']=='reset':raise RuntimeError('pulse failed')
    d.service(1,drive,log.append,tick=1,state={})
    with pytest.raises(RuntimeError):d.service(1,drive,log.append,tick=3,state={'outstanding':1})
    assert log==['reset-prepare','reset','reset-cleanup']
    assert not d.complete and not d.receipts


def test_plain_mailbox_cannot_ignore_phase_gate():
    with pytest.raises(ValueError,match='PhaseDriver'):MailboxDriver([event()])


def test_missing_wrong_and_early_phase_captures():
    e=event();r=dict(step=1,prepared_tick=1,reset_tick=3,state={'outstanding':1},complete=True)
    assert observe([e],[])['status']=='inconclusive'
    assert observe([],[])['status']=='inconclusive'
    assert observe([e],[dict(r,state={})])['status']=='inconclusive'
    assert observe([e],[dict(r,state={'outstanding':0})])['status']=='fail'
    assert observe([e],[dict(r,reset_tick=2)])['status']=='fail'
    assert observe([e,event(2)],[r,dict(r,step=2)])['status']=='fail'


def test_phase_generation_and_project_loading():
    c=campaign.load('examples/privilege/reset-inflight.json');rows=campaign.scenarios(c)
    assert len(rows)==15 and len({r['id'] for r in rows})==15
    assert {r['events'][0]['phase'] for r in rows}=={'fetch','load','store','trap','debug'}
    assert all(len(r['events'])==3 and r['reset_phase_contract']==r['events'] for r in rows)
    c['reset']['phases'][0]['state']={}
    with pytest.raises(ValueError,match='independent state'):programs(c)


def test_c1_identity_includes_requested_inputs_before_uniqueness(tmp_path,monkeypatch):
    import rvw.results
    elf=tmp_path/'one.elf';elf.write_bytes(b'elf')
    manifest=dict(schema='rvw.privilege-build/1',config={},scenarios=[dict(id='one',elf='one.elf',
        elf_sha256=campaign.digest(elf),bins=['reset'],options={'irq_schedule':[[3,1]]},stimulus_sha256='wanted')])
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    run_paths=[tmp_path/'a',tmp_path/'b']
    for path in run_paths:path.mkdir();(path/'result.json').write_text('{}')
    def run(path):
        return SimpleNamespace(elf_sha256=campaign.digest(elf),path=path,why_inconclusive=None,status='fail',artifacts={},
            extra=dict(irq_schedule=[[3,1]],stimulus_sha256='wanted' if path.name=='a' else 'other'))
    monkeypatch.setattr(rvw.results,'load_run',lambda p:run(p.parent))
    checked=campaign.check(tmp_path,tmp_path,'platform.json')
    assert checked['status']=='fail' and checked['scenarios'][0]['reason']=='C1 self-check failed'
    monkeypatch.setattr(rvw.results,'load_run',lambda p:run(run_paths[0]))
    assert campaign.check(tmp_path,tmp_path,'platform.json')['status']=='inconclusive'


def test_c1_needs_phase_capture_before_reference_pass(tmp_path,monkeypatch):
    import rvw.results
    elf=tmp_path/'one.elf';elf.write_bytes(b'elf')
    scenario=dict(id='one',elf='one.elf',elf_sha256=campaign.digest(elf),bins=['reset'],reset_phase_contract=[event()])
    (tmp_path/'manifest.json').write_text(json.dumps(dict(schema='rvw.privilege-build/1',scenarios=[scenario])))
    (tmp_path/'result.json').write_text('{}');(tmp_path/'trace').write_text('trace')
    artifacts={'rvfi_trace':'trace'}
    run=SimpleNamespace(elf_sha256=campaign.digest(elf),path=tmp_path,why_inconclusive=None,status='pass',artifacts=artifacts,extra={})
    monkeypatch.setattr(rvw.results,'load_run',lambda _:run)
    comparison=dict(status='match',trace_complete=True,end_status='pass',instructions=10,synchronized=0)
    monkeypatch.setattr(campaign,'run_group',lambda *a,**kw:SimpleNamespace(timed_out=False,returncode=0,stdout=json.dumps(comparison)))
    assert campaign.check(tmp_path,tmp_path,'platform.json')['status']=='inconclusive'
    receipt=dict(step=1,prepared_tick=1,reset_tick=3,state={'outstanding':1},complete=True)
    path=tmp_path/'phase.json';path.write_text(json.dumps([receipt]));artifacts['privilege_reset_phase']='phase.json'
    checked=campaign.check(tmp_path,tmp_path,'platform.json')
    assert checked['status']=='pass' and checked['scenarios'][0]['reset_phase_sha256']==campaign.digest(path)
    receipt['state']['outstanding']=0;path.write_text(json.dumps([receipt]))
    assert campaign.check(tmp_path,tmp_path,'platform.json')['status']=='fail'


def test_failed_preparation_releases_resources():
    d=PhaseDriver([event()]);log=[]
    def drive(action):
        log.append(action['kind'])
        if action['kind']=='reset-prepare':raise RuntimeError('prepare failed')
    with pytest.raises(RuntimeError):d.service(1,drive,log.append,tick=1,state={})
    assert log==['reset-prepare','reset-cleanup']
    assert not d.complete and d.prepared is None
