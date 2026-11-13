from rvw.privilege.timer_observe import check


def contract():
    return dict(latency_ticks=3,max_reference_time=100,phases={'armed':dict(compare=50,delta=60),'cleared':dict(compare=(1<<64)-1)})


def samples():
    return [dict(tick=i,phase='armed' if i<3 else 'cleared',phase_start=0 if i<3 else 3,reference_time=i,pending=i<3) for i in range(6)]


def test_independent_delta_and_clearing():
    assert check(contract(),samples())['status']=='pass'
    wrong=contract();wrong['phases']['armed']['delta']=0
    assert check(wrong,samples())['status']=='inconclusive'  # No correct event was observed before the phase ended.
    rows=samples();rows.insert(3,dict(tick=3,phase='armed',phase_start=0,reference_time=3,pending=True))
    for i,row in enumerate(rows):row['tick']=i
    assert check(wrong,rows)['status']=='fail'


def test_missing_and_late_witness():
    assert check(contract(),[])['status']=='inconclusive'
    rows=samples()[3:]
    assert check(contract(),rows)['status']=='inconclusive'
    rows=samples();rows[0]['pending']=None
    assert check(contract(),rows)['status']=='inconclusive'


def test_boundary_and_reference_precondition():
    rows=samples();rows[0]['reference_time']=101
    assert check(contract(),rows)['status']=='inconclusive'
    rows=samples();rows[0]['tick']=-1
    assert check(contract(),rows)['status']=='inconclusive'


def test_no_architectural_latency_is_assumed():
    c=contract();del c['latency_ticks']
    r=check(c,samples())
    assert r['status']=='pass' and r['latency_ticks'] is None


def test_phase_order_is_checked():
    rows=samples()[3:]+samples()[:3]
    for i,row in enumerate(rows):row['tick']=i
    assert check(contract(),rows)['status']=='fail'


def test_c1_timer_capture_gate(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    import rvw.results
    from rvw.privilege import campaign
    from test_privilege_campaign import make_build
    elf=make_build(tmp_path)
    manifest=json.loads((tmp_path/'manifest.json').read_text())
    manifest['scenarios'][0]['timer_contract']=contract()
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    (tmp_path/'result.json').write_text('{}')
    (tmp_path/'trace.jsonl').write_text('fixture')
    capture=tmp_path/'timer.json';capture.write_text(json.dumps(samples()))
    run=SimpleNamespace(elf_sha256=campaign.digest(elf),path=tmp_path,why_inconclusive=None,
        status='pass',extra={},artifacts={'rvfi_trace':'trace.jsonl','privilege_timer':'timer.json'})
    monkeypatch.setattr(rvw.results,'load_run',lambda _:run)
    match=dict(status='match',trace_complete=True,end_status='pass',instructions=1,synchronized=0)
    monkeypatch.setattr(campaign,'run_group',lambda *a,**k:SimpleNamespace(timed_out=False,returncode=0,stdout=json.dumps(match)))
    checked=campaign.check(tmp_path,tmp_path,'platform.json')
    assert checked['status']=='pass'
    assert checked['scenarios'][0]['timer_sha256']==campaign.digest(capture)
    bad=samples();bad.insert(3,dict(tick=3,phase='armed',phase_start=0,reference_time=3,pending=False))
    for i,row in enumerate(bad):row['tick']=i
    capture.write_text(json.dumps(bad))
    assert campaign.check(tmp_path,tmp_path,'platform.json')['status']=='fail'
    del run.artifacts['privilege_timer']
    assert campaign.check(tmp_path,tmp_path,'platform.json')['status']=='inconclusive'


def test_hex_counter_and_negative_offset_wrap():
    c=dict(latency_ticks=0,phases={'negative':dict(compare='0xffffffffffffff00',delta='-0x3c')})
    rows=[dict(phase='negative',tick=0,phase_start=0,reference_time='0x0',pending=True)]
    assert check(c,rows)['status']=='pass'
    rows[0]['pending']=False
    assert check(c,rows)['status']=='fail'
