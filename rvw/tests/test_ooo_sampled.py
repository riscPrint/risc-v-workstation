from dataclasses import asdict
import json
import pytest
from rvw.ooo.sampled import sampled
from rvw.csim.cli import simpoint_json

pytestmark=pytest.mark.fast


def test_shared_simpoint_join(tmp_path):
    from test_ooo import cfg,trace
    t=tmp_path/'trace';trace(t)
    c=tmp_path/'config';c.write_text(json.dumps(asdict(cfg())))
    points=simpoint_json(str(t),2,max_k=1)
    p=tmp_path/'points';p.write_text(json.dumps(points))
    r=sampled(c,t,p,tmp_path/'report',warmup=1,full=True)
    assert r['sampled_ipc']>0
    assert r['full_cycles']>0
    assert r['accuracy_status']=='inconclusive'
    assert sum(row['point']['weight'] for row in r['samples'])==1
    points['sha256']='bad';p.write_text(json.dumps(points))
    with pytest.raises(ValueError,match='hash'):
        sampled(c,t,p,tmp_path/'bad')


def test_full_trace_point_has_zero_sampling_gap(tmp_path):
    from test_ooo import cfg,trace
    t=tmp_path/'trace';trace(t)
    c=tmp_path/'config';c.write_text(json.dumps(asdict(cfg())))
    p=tmp_path/'points';p.write_text(json.dumps(simpoint_json(str(t),4,max_k=1)))
    r=sampled(c,t,p,tmp_path/'report',warmup=0,full=True)
    assert r['estimated_cycles']==r['full_cycles']
    assert r['signed_cycle_error_percent']==0


def test_raw_identity_and_bounded_decode(tmp_path,monkeypatch):
    from test_ooo import cfg,trace
    from rvw.ooo import windows
    t=tmp_path/'trace';trace(t)
    c=tmp_path/'config';c.write_text(json.dumps(asdict(cfg())))
    points=dict(schema='rvw.csim-simpoints/1',instructions=4,sha256='unused',
                source_c2_sha256=windows.digest(t),
                points=[dict(start_instruction=2,instructions=1,weight=1)])
    p=tmp_path/'points';p.write_text(json.dumps(points))
    calls=[];decode=windows._instruction
    def counted(row,*args):
        calls.append(row['order'])
        return decode(row,*args)
    monkeypatch.setattr(windows,'_instruction',counted)
    r=sampled(c,t,p,tmp_path/'report',warmup=1)
    assert calls==[1,2]
    assert r['samples'][0]['instret']==1
    points['source_c2_sha256']='0'*64;p.write_text(json.dumps(points))
    with pytest.raises(ValueError,match='hash'):
        sampled(c,t,p,tmp_path/'bad')


def test_windows_still_require_complete_trace(tmp_path):
    from test_ooo import trace
    from rvw.ooo.windows import collect
    t=tmp_path/'trace';trace(t,end=False)
    with pytest.raises(ValueError,match='end'):
        collect(t,[dict(start_instruction=0,instructions=1)],0)
