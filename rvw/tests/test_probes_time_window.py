"""A complete probe stream retains quiet clock samples in its Kanata output."""
import json
import pytest
from rvw.probes import api
from rvw.perf.kanata import read

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('bounded,complete,expected', [(True, True, (1, 10)), (False, True, (5, 6)), (False, False, (5, 6))])
def test_quiet_prefix_and_tail_need_explicit_bounds(tmp_path, bounded, complete, expected):
    rows = [{'schema': 'rvw.probe-events/1', 'identity': {}, 'probes': [
        {'id': 0, 'kind': 'stage', 'name': 'C', 'fields': [['id', 8], ['pc', 32]], 'meta': {'stage': 'C'}},
        {'id': 1, 'kind': 'retire', 'name': 'commit', 'fields': [['id', 8]], 'meta': {}},
    ]}, [5, 0, 7, 0x1000], [6, 1, 7]]
    if complete:
        end = {'end': True, 'cycles': 10, 'counters': {}, 'events': {'0': 1, '1': 1}}
        if bounded:
            end.update(first_cycle=1, last_cycle=10)
        rows.append(end)
    events = tmp_path / 'events.jsonl'
    events.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    output = tmp_path / 'trace.log'
    api.run_convert(events, 'kanata', output)
    trace = read(output)
    assert (trace.start, trace.end) == expected
    assert len(trace.instructions) == 1
