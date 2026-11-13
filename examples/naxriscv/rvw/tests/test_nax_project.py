"""Project selection, regression suites and the Spike platform, without a Scala build."""
import json
from pathlib import Path
import shutil

import pytest

from rvw.common.project import find_project, load_project
from rvw.regress.config import load_config

pytestmark = pytest.mark.fast

EXAMPLE = Path(__file__).resolve().parents[2]


def test_copied_project_uses_core_owned_paths(tmp_path, monkeypatch):
    core = tmp_path / 'separate core'
    core.mkdir()
    shutil.copy2(EXAMPLE / 'rvw.toml', core / 'rvw.toml')
    shutil.copytree(EXAMPLE / 'rvw', core / 'rvw',
                    ignore=shutil.ignore_patterns('target', 'out', '__pycache__'))
    monkeypatch.setenv('RVW_HOME', str(tmp_path / 'installed workstation'))
    monkeypatch.delenv('RVW_PROJECT', raising=False)
    monkeypatch.chdir(core / 'rvw' / 'programs')
    assert find_project() == core / 'rvw.toml'
    project = load_project()
    config = load_config(str(project.path))
    assert config.source_repo == core
    assert config.adapter == [str(core / 'rvw/run.sh')]
    assert project.get('cosim', 'platform') == core / 'rvw/platform.json'


def test_platform_matches_the_configuration():
    platform = json.loads((EXAMPLE / 'rvw/platform.json').read_text())
    assert platform['isa'] == 'rv32ima_zicsr_zifencei'
    assert platform['privilege_modes'] == 'MSU'
    assert platform['reset_pc'] == '0x80000000'
    assert platform['ram'] == [{'base': '0x80000000', 'size': '0x1000000'}]


def test_launcher_selects_the_pinned_spinal_source():
    run = (EXAMPLE / 'rvw/run.sh').read_text()
    assert 'export RVW_SPINAL_SOURCE="$NAXRISCV/ext/SpinalHDL"' in run
    assert "'++2.12.18!'" in run
    assert '-DVL_TIME_CONTEXT' in run
