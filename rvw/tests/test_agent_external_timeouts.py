"""Disconnect and wall-clock timeout integration cases belong to the slow set."""
import json
import pytest
from test_agent_external import PACK, CLIENT, run_trial

pytestmark = pytest.mark.slow


@pytest.mark.parametrize('mode', ['disconnect', 'timeout'])
@pytest.mark.slow
def test_external_partial_transcript_survives_disconnect_or_timeout(tmp_path, mode):
    report = run_trial(PACK, 'task-03', CLIENT + [mode], tmp_path / mode,
                       budget_s=8 if mode == 'timeout' else 20)
    assert not report['attempts'][0]['complete']
    assert report['summary']['tasks'] == report['summary']['censored_root_causes'] == 1
    assert report['summary']['correct_fixes'] == 0
    assert report['attempts'][0]['timed_out'] == (mode == 'timeout')
    saved = json.loads((tmp_path / mode / 'results.json').read_text())
    assert saved['attempts'] == report['attempts']
    if mode == 'disconnect':
        assert saved['tasks'][0]['transcript'][0]['tool'] == 'bench_inspect'
