"""Bundled ACT4 config checks must not build or run BOOM."""
import json
from pathlib import Path
import pytest
from rvw.regress import act4
from rvw.regress.config import load_config

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT/'rvw/configs/act4/boom/profile.json'


def test_boom_profile_plan_does_not_execute_tools(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('config-only ACT4 check attempted a subprocess')
    monkeypatch.setattr(act4, 'run_group', forbidden)
    plan = act4.selection(PROFILE)
    assert plan['isa'] == 'rv64imafdc_zicsr_zifencei_zba_zbb_zbs_zicntr_zihpm'
    assert plan['privilege_modes'] == 'MSU'
    assert {'i', 'm', 'a', 'f', 'd', 'c', 'sm', 's', 'u', 'sv39', 'zihpm'} <= set(plan['extensions'])
    assert plan['test_selection'] == 'all-applicable'
    assert plan['include_priv_tests'] is True
    assert plan['evidence'] == 'selection only; no DUT execution'


def test_boom_profile_map_and_reference_agree():
    data, platform, _ = act4.description(PROFILE)
    sail = json.loads((PROFILE.parent/'sail.json').read_text())
    assert platform.ram == [(0x80000000, 0x10000000)]
    assert platform.reset_pc == 0x80000000
    assert data['params']['MXLEN'] == platform.xlen == sail['base']['xlen'] == 64
    assert data['params']['PHYS_ADDR_WIDTH'] == sail['memory']['physaddr_bits'] == 32
    assert data['params']['NUM_USABLE_PMP_ENTRIES'] == sail['memory']['pmp']['usable_count'] == platform.pmp_regions == 8
    assert sail['extensions']['Sv39']['supported'] is True
    assert sail['extensions']['Zihpm']['supported'] is True
    assert sail['extensions']['Zicntr']['supported'] is True
    assert platform.csr_masks == {}
    model_map = [(int(r['base']['value'], 0), int(r['size']['value'], 0)) for r in sail['memory']['regions']]
    assert model_map == platform.mmio + platform.ram
    assert sail['platform']['clint']['size'] == 0x10000


def test_boom_suite_uses_the_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv('ACT4_PROJECT_OUT', str(tmp_path/'act4'))
    config = load_config('boom')
    suite = config.suite('act4-project')
    assert suite.configs == ['small']
    assert suite.dir == tmp_path/'act4/work/rvw-act4/elfs'
    assert suite.act4_manifest == tmp_path/'act4/manifest.json'
    assert config.suite('act4').act4_manifest is None


def test_boom_signature_halt_and_reset_are_explicit():
    macros = (PROFILE.parent/'rvmodel_macros.h').read_text()
    linker = (PROFILE.parent/'link.ld').read_text()
    assert '#define STANDARD_SM_SUPPORTED' in macros
    assert '#define RVMODEL_BOOT_TO_MMODE' not in macros
    assert 'li x1, 1' in macros and 'li x1, 3' in macros
    assert '.global tohost' in macros
    assert 'ENTRY(__rvw_reset)' in linker
    assert 'LONG(0x34001073)' in linker
    assert 'LONG(0x30501073)' in linker
    assert '.text.init   TEST_BASE + 0x40' in linker
