"""Check a native capture without starting a simulator or a build.

Set RVW_BOOM_CAPTURE to a small run directory with C1, C2 and probe events.
"""
import json
import os
from pathlib import Path
import pytest
from rvw.probes.events import read
from rvw.probes.convert import bp_events


@pytest.fixture
def capture():
    directory = os.environ.get('RVW_BOOM_CAPTURE')
    if not directory:
        pytest.skip('RVW_BOOM_CAPTURE is required; no native capture was supplied')
    path = Path(directory)
    return path, read(path/'probe-events.jsonl'), json.loads((path/'result.json').read_text())


def test_commit_accounting_and_full_rob_bounds(capture):
    _, stream, c1 = capture
    totals = stream.counters
    assert totals['commits'] == totals['architectural_commits'] + totals['predicated_off_commits']
    assert totals['rob_head_occupancy'] <= totals['rob_occupancy']
    # The collector stores counter integrals, not individual cycle samples.
    assert 0 < totals['rob_occupancy'] <= 32 * c1['cycles']
    assert c1['config'] == 'small' and c1['status'] == 'pass'
    if Path(c1['elf']).name == 'sfb.elf':
        assert totals['predicated_off_commits'] > 0


def test_conditional_predictions_align_with_architectural_stream(capture, tmp_path):
    path, stream, _ = capture
    result = bp_events(stream, path/'rvfi.jsonl', tmp_path/'branches.jsonl', probe='conditional_commit_0')
    rows = [json.loads(line) for line in (tmp_path/'branches.jsonl').read_text().splitlines()][1:]
    assert result['rows'] and all('predicted_taken' in row for row in rows)
    # These branch-heavy smoke programs must expose a repaired prediction.
    assert any(row['predicted_taken'] != row['taken'] for row in rows)
    assert any(p.name.startswith('fetch_prediction_') for p in stream.probes)
    assert any(p.name.startswith('execute_branch_') for p in stream.probes)
    assert any(p.name == 'mispredict_redirect' for p in stream.probes)
