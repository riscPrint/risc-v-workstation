"""Recall: a missing switch default becomes a Yosys latch, not a flip-flop."""
from pathlib import Path
import shutil
import pytest
from rvw.query.hdl import build_hdl
from rvw.lint.rules import run


@pytest.mark.native_light('Yosys')
def test_lowered_latch_is_reported(tmp_path):
    if not shutil.which('yosys'):
        pytest.skip('Yosys is not installed')
    source = Path(__file__).parent / 'fixtures/lint/incomplete_switch.v'
    db = tmp_path / 'design.db'
    build_hdl([source], 'IncompleteSwitch', db)
    result = run(db, None)
    assert any(f['rule'] == 'lint.latch' and f['endpoint'] == 'result' for f in result['findings'])
