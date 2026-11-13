"""Validate the bundled small project without elaborating the core."""
import json
from pathlib import Path
import pytest
from rvw.ooo.project import configuration

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_small_project_has_shared_queue_dimensions_and_predictor():
    data = json.loads((ROOT / 'examples/boom/ooo/small.json').read_text())
    baseline = json.loads((ROOT / 'examples/boom/arch/small.json').read_text())
    assert data['cpu'] == baseline['cpu']
    assert data['queues'] == baseline['queues']
    config = configuration(data)
    assert config.rob_entries == data['cpu']['numROBEntries'] == 32
    assert config.issue_entries == sum(q['entries'] for q in data['queues']) == 32
    assert config.commit_width == config.rename_width == 1
    study = json.loads((ROOT / 'examples/boom/csim/tage-l.json').read_text())
    assert config.components == study


def test_projection_refuses_conflicting_commit_width():
    data = json.loads((ROOT / 'examples/boom/ooo/small.json').read_text())
    data['ooo']['commit_width'] = 2
    with pytest.raises(ValueError, match='commit_width conflicts'):
        configuration(data)
