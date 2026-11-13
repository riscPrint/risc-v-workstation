import hashlib
import json
import pytest
from rvw.formal.state_selection import select


def test_hole_priority_and_trace_binding(tmp_path):
    trace = tmp_path / 'trace.vcd'
    trace.write_bytes(b'captured')
    plan = tmp_path / 'states.json'
    plan.write_text(json.dumps({'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
        'holes': ['full', 'wrap'], 'states': [{'cycle': 1, 'targets': []},
        {'cycle': 7, 'targets': ['full']}, {'cycle': 8, 'targets': ['wrap']}]}))
    cycles, detail = select(plan, trace, 1, 10, 2)
    assert cycles == [7, 8]
    assert detail['unrepresented_targets'] == []
    trace.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        select(plan, trace, 1, 10, 2)


def test_reject_insufficient_candidates(tmp_path):
    trace = tmp_path / 'trace'
    trace.write_bytes(b'')
    plan = tmp_path / 'states'
    plan.write_text(json.dumps({'trace_sha256': hashlib.sha256(b'').hexdigest(),
                               'holes': ['x'], 'states': [{'cycle': 3, 'targets': ['x']}]}))
    with pytest.raises(ValueError, match='not enough'):
        select(plan, trace, 1, 2, 1)
