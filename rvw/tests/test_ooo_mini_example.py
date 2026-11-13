"""Check the core-owned project's launch contract and declared scope."""
import json
from pathlib import Path
import tomllib
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2] / 'examples/ooo-mini'


def test_project_owns_sources_and_configs():
    project = tomllib.loads((ROOT / 'rvw.toml').read_text())
    assert project['core']['source_repo'] == '.'
    assert project['core']['configs'] == ['default', 'rob16']
    assert project['core']['jobs'] <= 3
    assert project['core']['input_complete']
    assert project['core']['cache_paths']
    assert project['core']['input_env']
    assert project['core']['input_tools']
    assert not project['core']['identity']
    assert (ROOT / project['core']['adapter']).is_file()
    assert '1.15.0' in (ROOT / 'build.sbt').read_text()


def test_platform_declares_only_supported_machine_features():
    platform = json.loads((ROOT / 'rvw/platform.json').read_text())
    assert platform['xlen'] == 32
    assert platform['privilege_modes'] == 'M'
    assert platform['irq_inputs'] == []
    assert platform['misaligned']['load'] == 'emulate'
    assert platform['misaligned']['store'] == 'emulate'
