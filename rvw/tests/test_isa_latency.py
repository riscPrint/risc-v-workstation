import json
import pytest
from rvw.formal.isa_latency import configure
from rvw.formal.isa import bounded_rows
pytestmark = pytest.mark.fast


def test_measured_multicycle_bound(tmp_path):
    trace = tmp_path/'trace.jsonl'
    trace.write_text('\n'.join(json.dumps(dict(order=i, cycle=c)) for i,c in enumerate([9,15,21])))
    cfg = configure({'depth':24}, trace)
    assert cfg['depth'] == 17
    assert cfg['latency_measurement']['max_interval'] == 6
    assert configure({'depth':24})['depth'] == 24


def test_missing_trace_is_actionable():
    with pytest.raises(ValueError, match='--trace'):
        configure({})


def test_timeout_action_is_distinct_from_unreachable():
    suite = dict(bounded_depth=10, tests=[dict(id='add',status='timeout'),dict(id='lw',status='pass',inconclusive='unreachable')])
    rows = bounded_rows(suite)
    assert '--timeout' in rows[0]['action']
    assert 'RVFI order/valid' in rows[1]['action']
    assert all(r['status']=='inconclusive' for r in rows)
