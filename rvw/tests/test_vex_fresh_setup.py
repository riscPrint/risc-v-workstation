"""The public project must load after the documented copy and unset steps."""
from pathlib import Path

import pytest
from rvw.regress.config import load_config

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / 'examples/vexriscv'


@pytest.mark.parametrize('external', [False, True])
def test_copied_project_source_selection(tmp_path, monkeypatch, external):
    monkeypatch.setenv('RVW_HOME', str(ROOT))
    monkeypatch.delenv('VEXRISCV', raising=False)
    project = tmp_path / 'rvw.toml'
    project.write_text((EXAMPLE / 'rvw.toml').read_text())
    source = tmp_path
    if external:
        source = tmp_path / 'captured-core'
        source.mkdir()
        monkeypatch.setenv('VEXRISCV', str(source))
    config = load_config(project=project)
    assert config.source_repo == source
