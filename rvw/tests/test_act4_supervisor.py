"""The supervisor ACT4 profile must preserve standard boot checks."""
import json
from pathlib import Path
import pytest
from rvw.regress.act4 import description, selection
from rvw.regress.config import load_config

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT/'examples/vexiiriscv/rvw/act4-supervisor/profile.json'


def test_supervisor_selection_includes_privileged_directories():
    data, platform, _ = description(PROFILE)
    plan = selection(PROFILE)
    assert platform.privilege_modes == 'MSU'
    assert platform.isa == 'rv32ima_zicsr_zifencei'
    assert plan['test_selection'] == 'all-applicable'
    assert plan['include_priv_tests'] is True
    assert {'sm','s','u','sv32'} <= set(plan['extensions'])
    assert data['params']['ASID_WIDTH'] == 9


def test_reference_map_and_standard_boot():
    data, platform, _ = description(PROFILE)
    sail = json.loads((PROFILE.parent/'sail.json').read_text())
    assert sail['memory']['physaddr_bits'] == 32
    assert sail['memory']['pmp']['usable_count'] == platform.pmp_regions == 8
    assert sail['memory']['asidlen'] == data['params']['ASID_WIDTH']
    assert sail['extensions']['S']['supported'] is True
    assert sail['extensions']['U']['supported'] is True
    assert sail['extensions']['Sv32']['supported'] is True
    macros = (PROFILE.parent/'rvmodel_macros.h').read_text()
    assert '#define STANDARD_SM_SUPPORTED' in macros
    assert '#define RVMODEL_BOOT_TO_MMODE' not in macros


def test_suite_uses_supervisor_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv('VEXIIRISCV', str(tmp_path))
    monkeypatch.setenv('RVW_HOME', str(ROOT))
    suite = load_config(project=ROOT/'examples/vexiiriscv').suite('act4-supervisor')
    assert suite.configs == ['rv32imasu']
    assert suite.act4_manifest.name == 'manifest.json'
