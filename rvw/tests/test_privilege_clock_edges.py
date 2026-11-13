import json
from types import SimpleNamespace
import pytest
from rvw.privilege.clock_edges import observe
from rvw.privilege.dvfs import plan,programs
from rvw.privilege import campaign

pytestmark=pytest.mark.fast


def fixture():
    c=dict(states={'low':dict(frequency_hz=50,voltage_uv=800),'high':dict(frequency_hz=100,voltage_uv=1000)},
           sequence=['low','high','low'],clock_measure=dict(reference_hz=1000,min_high_ticks=5,min_low_ticks=5,
             period_tolerance_ticks=0,settle_ticks=10,max_switch_ticks=50,max_edge_gap_ticks=40))
    rows=[]
    for transition in plan(c):
        state=dict(c['states'][transition['source']]);target=c['states'][transition['target']]
        start=80 if transition['step']==1 else 180
        for i,phase in enumerate(transition['phases']):
            if phase=='voltage_ready':state['voltage_uv']=target['voltage_uv']
            if phase=='clock_changed':state['frequency_hz']=target['frequency_hz']
            rows.append(dict(tick=start+10*i,step=transition['step'],phase=phase,clock_ready=True,voltage_ready=True,**state))
    edges=[]
    for start,end,period in ((0,100,20),(100,190,10),(190,301,20)):
        for tick in range(start,end,period):
            edges.append(dict(tick=tick,level=True))
            if tick+period//2<=300:edges.append(dict(tick=tick+period//2,level=False))
    capture=dict(reference_hz=1000,complete=True,start_tick=0,end_tick=300,edges=edges)
    return c,rows,capture


def test_measured_periods_and_pulses():
    result=observe(*fixture())
    assert result['status']=='pass'
    assert [w['period_ticks'] for w in result['windows']]==['20','10','20']


def test_runt_gap_wrong_period_and_switch_bound():
    c,s,x=fixture();next(e for e in x['edges'] if e['tick']==105)['tick']=101
    assert 'too short' in observe(c,s,x)['reason']
    c,s,x=fixture();x['edges']=[e for e in x['edges'] if e['tick'] not in (130,135)]
    r=observe(c,s,x);assert r['status']=='fail' and 'period' in r['reason']
    c,s,x=fixture();x['edges']=[e for e in x['edges'] if not 100<=e['tick']<190]
    assert 'gap exceeds' in observe(c,s,x)['reason']
    c,s,x=fixture();c['clock_measure']['max_switch_ticks']=20
    assert 'acknowledgement' in observe(c,s,x)['reason']


def test_missing_capture_short_window_and_unknown_edge():
    c,s,x=fixture()
    assert observe(c,s,None)['status']=='inconclusive'
    x['complete']=False;assert observe(c,s,x)['status']=='inconclusive'
    c,s,x=fixture();x['edges'][1]['level']=None
    assert observe(c,s,x)['status']=='inconclusive'
    c,s,x=fixture();x['end_tick']=230;x['edges']=[e for e in x['edges'] if e['tick']<=230]
    assert observe(c,s,x)['status']=='inconclusive'
    c,s,x=fixture();x['edges']=[]
    assert observe(c,s,x)['status']=='fail'


def test_invalid_clock_assumption_rejected_at_generation():
    c,_,_=fixture();c['clock_measure']['reference_hz']=0
    with pytest.raises(ValueError):programs({'dvfs':c})


def test_c1_clock_edges_are_required_and_bound(tmp_path,monkeypatch):
    import rvw.results
    contract,samples,capture=fixture();elf=tmp_path/'one.elf';elf.write_bytes(b'elf')
    scenario=dict(id='one',elf=elf.name,elf_sha256=campaign.digest(elf),bins=['dvfs'],dvfs_contract=contract)
    (tmp_path/'manifest.json').write_text(json.dumps(dict(schema='rvw.privilege-build/1',scenarios=[scenario])))
    (tmp_path/'result.json').write_text('{}');(tmp_path/'trace').write_text('trace')
    (tmp_path/'handshake.json').write_text(json.dumps(samples))
    artifacts={'rvfi_trace':'trace','privilege_dvfs':'handshake.json'}
    run=SimpleNamespace(elf_sha256=campaign.digest(elf),path=tmp_path,why_inconclusive=None,status='pass',extra={},artifacts=artifacts)
    monkeypatch.setattr(rvw.results,'load_run',lambda _:run)
    comparison=dict(status='match',trace_complete=True,end_status='pass',instructions=100,synchronized=0)
    monkeypatch.setattr(campaign,'run_group',lambda *a,**kw:SimpleNamespace(timed_out=False,returncode=0,stdout=json.dumps(comparison)))
    assert campaign.check(tmp_path,tmp_path,'platform.json')['status']=='inconclusive'
    edgefile=tmp_path/'edges.json';edgefile.write_text(json.dumps(capture));artifacts['privilege_clock_edges']='edges.json'
    result=campaign.check(tmp_path,tmp_path,'platform.json')
    assert result['status']=='pass' and result['scenarios'][0]['clock_edges_sha256']==campaign.digest(edgefile)
    next(e for e in capture['edges'] if e['tick']==105)['tick']=101;edgefile.write_text(json.dumps(capture))
    assert campaign.check(tmp_path,tmp_path,'platform.json')['status']=='fail'


def test_reference_tick_recorder_marks_gaps_and_unknowns():
    from rvw.privilege.clock_edges import EdgeRecorder
    r=EdgeRecorder(1000)
    for tick,level in enumerate([False,False,True,True,False]):r.sample(tick,level)
    assert r.capture()==dict(reference_hz=1000,complete=True,start_tick=0,end_tick=4,
                             edges=[dict(tick=2,level=True),dict(tick=4,level=False)])
    r.sample(6,True);assert not r.capture()['complete']
    r=EdgeRecorder(1000);r.sample(0,False);r.sample(1,None);r.sample(2,True)
    assert not r.capture()['complete'] and not r.capture()['edges']
    assert not EdgeRecorder(1000).capture()['complete']
