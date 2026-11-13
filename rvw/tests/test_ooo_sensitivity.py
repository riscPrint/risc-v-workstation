import json
from dataclasses import asdict
from pathlib import Path
import pytest
from rvw.ooo.sensitivity import sensitivity
from rvw.ooo.core import Config

pytestmark=pytest.mark.fast


def test_rank_latency_on_dependent_work(tmp_path):
    from test_ooo import trace
    t=tmp_path/'trace.jsonl'; trace(t,insn='0x108093')  # ADDI x1,x1,1
    c=Config(2,8,2,16,2,8,4,4,2,{'alu':4})
    (tmp_path/'c.json').write_text(json.dumps(asdict(c)))
    p=tmp_path/'plan.json'
    p.write_text(json.dumps(dict(schema='rvw.ooo-sensitivity-plan/1',config='c.json',
                    traces=['trace.jsonl'],parameters=['latencies.alu','rob_entries'],fraction=0.25)))
    r=sensitivity(p,tmp_path/'out')
    assert r['ranking'][0]['parameter']=='latencies.alu'
    assert r['ranking'][0]['best_ipc_gain']>0
    assert r['ranking'][1]['sensitivity']==0
    assert Path(tmp_path/'out').exists()


def test_invalid_candidate_stays_explicit(tmp_path):
    from test_ooo import trace
    t=tmp_path/'trace.jsonl';trace(t)
    c=Config(1,8,1,16,1,8,4,4,1,{'alu':1})
    (tmp_path/'c.json').write_text(json.dumps(asdict(c)))
    p=tmp_path/'p.json';p.write_text(json.dumps(dict(schema='rvw.ooo-sensitivity-plan/1',config='c.json',
                            traces=['trace.jsonl'],parameters=['issue_width'])))
    r=sensitivity(p,tmp_path/'out')
    assert r['ranking'][0]['trials'][0]['status']=='unsupported'
    spec=json.loads(p.read_text());spec['parameters']=['no_field'];p.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='positive numeric'):
        sensitivity(p,tmp_path/'bad')
