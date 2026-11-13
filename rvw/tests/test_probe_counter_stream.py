import json
import pytest
from rvw.probes.events import read
pytestmark = pytest.mark.fast


def test_counter_only_read_keeps_validation(tmp_path):
    path = tmp_path / 'events.jsonl'
    header = {'schema': 'rvw.probe-events/1', 'probes': [
        {'id': 0, 'kind': 'counter', 'name': 'counter', 'fields': [['value',32]]}]}
    rows = [header, [1,0,1], [2,0,2], {'end': True, 'cycles': 2, 'counters': {'counter':3}}]
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    assert read(path, retain_rows=False).rows == []
    assert read(path, retain_rows=False).counters == read(path).counters
    rows[2] = [0,0,2]
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError, match='decrease'):
        read(path, retain_rows=False)
