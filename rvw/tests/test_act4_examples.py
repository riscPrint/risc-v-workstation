"""Project ACT4 declarations. Native qualification is recorded separately."""
import json
from pathlib import Path
import pytest
from rvw.regress.act4 import description, selection
from rvw.regress.config import load_config

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('project', ['vexriscv', 'vexiiriscv'])
def test_instruction_profile(project):
    root = ROOT/'examples'/project
    profile = root/'rvw/act4/profile.json'
    data, platform, chosen = description(profile)
    assert set(chosen) == {'i','m','zmmul','zicsr','zifencei'}
    assert platform.privilege_modes == 'M'
    sail = json.loads((profile.parent/'sail.json').read_text())
    assert sail['base']['xlen'] == 32
    assert sail['extensions']['S']['supported'] is False
    ram = [r for r in sail['memory']['regions'] if r['include_in_device_tree']]
    assert [(int(r['base']['value'],16),int(r['size']['value'],16)) for r in ram] == platform.ram
    # No program-driven IRQ device exists. Do not invent one in DUT macros.
    macros = (profile.parent/'rvmodel_macros.h').read_text()
    assert 'RVMODEL_MTIMECMP_ADDRESS' not in macros
    assert all(data['params'][n] is False for n in ('MEI_INTR_IMPL','MSI_INTR_IMPL','MTI_INTR_IMPL'))


@pytest.mark.parametrize("project,env", [("vexriscv","VEXRISCV"),("vexiiriscv","VEXIIRISCV")])
def test_suite_binds_build_manifest(monkeypatch, tmp_path, project, env):
    monkeypatch.setenv(env, str(tmp_path))
    monkeypatch.setenv("RVW_HOME", str(ROOT))
    root = ROOT/'examples'/project
    suite = load_config(project=root).suite('act4')
    assert suite.act4_manifest == root/'rvw/out/act4/manifest.json'
