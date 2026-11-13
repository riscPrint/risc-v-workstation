"""The same selector binds Spinal and mapped Verilog instruction suites."""
from pathlib import Path
import pytest
from rvw.regress.act4 import description
from rvw.regress.config import load_config

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('core,groups,config', [
    ('naxriscv', {'i','m','zmmul','a','zaamo','zalrsc','zicsr','zifencei'}, 'rv32imasu'),
    ('picorv32', {'i','m','zmmul'}, 'default'),
])
def test_generic_instruction_selection(monkeypatch, core, groups, config):
    monkeypatch.setenv('RVW_HOME',str(ROOT))
    monkeypatch.setenv('NAXRISCV',str(ROOT))
    project=ROOT/'examples'/core
    data,platform,selected=description(project/'rvw/act4/profile.json')
    assert set(selected)==groups
    assert platform.privilege_modes=='M'
    suite=load_config(project=project).suite('act4')
    assert suite.configs==[config]
    assert suite.act4_manifest==project/'rvw/out/act4/manifest.json'
    if core=='picorv32':
        assert 'csrw' not in (project/'rvw/act4/rvmodel_macros.h').read_text()
        assert 'LONG(0x34001073)' not in (project/'rvw/act4/link.ld').read_text()
    else:
        assert data['params']['ARCH_ID_VALUE']==5
