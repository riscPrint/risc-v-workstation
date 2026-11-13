"""Resetless flip-flops must not disappear into per-cell BOOT domains."""
from pathlib import Path
import shutil
import pytest
from rvw.query.hdl import build_hdl
from rvw.lint.rules import run


@pytest.mark.native_light('Yosys')
def test_resetless_valid_inventory(tmp_path):
    if not shutil.which('yosys'):
        pytest.skip('Yosys is not installed')
    db = tmp_path / 'design.db'
    build_hdl([Path(__file__).parent / 'fixtures/lint/resetless_valid.v'], 'ResetlessValid', db)
    r = run(db, None)
    assert any(f['rule'] == 'lint.no_reset' and f['endpoint'] == 'valid' for f in r['findings'])
