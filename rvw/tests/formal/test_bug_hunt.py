import hashlib
from pathlib import Path
import pytest
from rvw.formal import bug_hunt as b


def plan(tmp_path):
    p = tmp_path / 'model.sv'
    p.write_bytes(b'model')
    return {'top': 'model', 'sources': [{'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}],
            'depths': [4, 8], 'seeds': [1, 7], 'engines': ['aiger:rIC3', 'abc:bmc3']}


def test_schedule_and_frozen_sources(tmp_path, monkeypatch):
    m = plan(tmp_path)
    seen = []
    def race(child, root, out, **kw):
        assert (root / '0.input').read_bytes() == b'model'
        (tmp_path / 'model.sv').write_bytes(b'changed')
        seen.append((child['depth'], child['engines'][0], child['ric3_seed']))
        return {'status': 'inconclusive', 'rows': [{'status': 'bounded_pass'}]}
    monkeypatch.setattr(b, 'race', race)
    r = b.hunt(m, tmp_path, tmp_path / 'out')
    assert len(seen) == 6
    assert seen[:3] == [(4, 'aiger:rIC3', 1), (4, 'aiger:rIC3', 7), (4, 'abc:bmc3', None)]
    assert r['status'] == 'inconclusive' and r['unstarted'] == []


def test_failure_stops_and_retains_unstarted(tmp_path, monkeypatch):
    monkeypatch.setattr(b, 'race', lambda *a, **kw: {'status': 'fail', 'rows': []})
    r = b.hunt(plan(tmp_path), tmp_path, tmp_path / 'out')
    assert r['status'] == 'fail' and len(r['unstarted']) == 5


def test_budget_stops_before_engine_start(tmp_path, monkeypatch):
    ticks = iter([0, 61])
    monkeypatch.setattr(b.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(b, 'race', lambda *a, **kw: pytest.fail('budget expired'))
    r = b.hunt(plan(tmp_path), tmp_path, tmp_path / 'out')
    assert r['stop_reason'] == 'budget_exhausted' and len(r['unstarted']) == 6
