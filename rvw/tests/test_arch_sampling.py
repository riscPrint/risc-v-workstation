import json
import pytest
from rvw.arch.sampling import vectors, sample, sampled_cpi
from test_ooo import trace


def phases(path):
    trace(path)
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    template = rows[1]
    pcs = [0, 4, 0, 4, 16, 20, 16, 20, 32]
    body = [{**template, "order": i, "cycle": i, "pc": hex(pc),
             "pc_next": hex(pcs[i+1] if i+1 < len(pcs) else pc+4)} for i, pc in enumerate(pcs)]
    path.write_text("".join(json.dumps(r)+"\n" for r in
        [rows[0], *body, dict(event="end", cycle=len(pcs), status="pass")]))


def test_phase_selection_and_weighted_cpi(tmp_path):
    p = tmp_path / 'trace'
    phases(p)
    plan = sample(p, tmp_path / 'plan', interval=2, clusters=3, warmup=3)
    assert plan['instret'] == 9
    assert len(plan['samples']) == 3
    assert sum(s['weight'] for s in plan['samples']) == pytest.approx(1)
    assert sorted(s['represented_instructions'] for s in plan['samples']) == [1, 4, 4]
    for s in plan['samples']:
        assert s['actual_warmup'] == min(3, s['start'])
        assert s['capture'] + s['actual_warmup'] == s['start']
    observations = {str(s['cluster']): dict(instret=s['end']-s['start'], cycles=2*(s['end']-s['start']))
                    for s in plan['samples']}
    result = sampled_cpi(plan, observations, 18)
    assert result['sampled_cpi'] == 2
    assert result['signed_cpi_bias_percent'] == 0
    assert sample(p, tmp_path / 'repeat', interval=2, clusters=3, warmup=3) == plan
    with pytest.raises(FileExistsError):
        sample(p, tmp_path / 'plan', interval=2)
    with pytest.raises(ValueError, match='every'):
        sampled_cpi(plan, {}, 18)


def test_partial_intervals_and_single_phase(tmp_path):
    p = tmp_path / 'trace'
    trace(p)
    r = sample(p, tmp_path / 'plan', interval=3, clusters=10)
    assert len(r['samples']) == 1
    assert r['samples'][0]['weight'] == 1
    assert [v['end']-v['start'] for v in r['intervals']] == [3, 1]


@pytest.mark.parametrize('kw', [dict(interval=0), dict(clusters=0), dict(warmup=-1)])
def test_invalid_settings(tmp_path, kw):
    p = tmp_path / 'trace'
    trace(p)
    with pytest.raises(ValueError):
        sample(p, tmp_path / 'out', **kw)


def test_reject_incomplete_and_failed_traces(tmp_path):
    p = tmp_path / 'trace'
    trace(p, end=False)
    with pytest.raises(ValueError):
        vectors(p, 2)
    trace(p)
    p.write_text(p.read_text().replace('"status": "pass"', '"status": "fail"'))
    with pytest.raises(ValueError):
        vectors(p, 2)
