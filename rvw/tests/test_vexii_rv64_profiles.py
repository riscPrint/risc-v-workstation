"""RV64 profile selection must retain the RV32 default and distinct platforms."""
import json
from pathlib import Path
import tomllib
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2] / "examples/vexiiriscv"


def test_rv64_profiles_keep_machine_and_supervisor_platforms_separate():
    default = tomllib.loads((ROOT / 'rvw.toml').read_text())
    assert default['core']['default_config'] == 'rv32im'
    for suffix, config, privilege, pmp in [('64m', 'rv64ima', 'M', 0),
                                          ('64', 'rv64imasu', 'MSU', 8)]:
        project = tomllib.loads((ROOT / f'rvw{suffix}.toml').read_text())
        assert config in project['core']['configs']
        platform = json.loads((ROOT / project['cosim']['platform']).read_text())
        assert platform['xlen'] == 64
        assert platform['isa'] == 'rv64ima_zicsr_zifencei'
        assert platform['privilege_modes'] == privilege
        assert platform['pmp_regions'] == pmp
        suite = project['suites']['isa-rv64']
        assert suite['configs'] == [config]
        assert '^rv64ui-p-ma_data$' in suite['exclude']



def test_machine_plan_excludes_paging_and_pmp():
    from rvw.regress.commands.applicability import plan
    rows = plan(ROOT / 'rvw/features64m.json')['suites']
    selected = {row['name'] for row in rows if row['applicable']}
    assert {'lrsc-rv64', 'amo-rv64', 'fence-rv64', 'fence-i-rv64'} <= selected
    assert not any(name.startswith('mmu-') for name in selected)
    assert 'pmp' not in selected
    assert 'privilege-controls' not in selected
    assert 'amo-fault-rv64' not in selected


def test_act4_profiles_declare_rv64_and_sv39():
    from rvw.regress.act4 import description, selection
    for suffix in ['64m', '64su']:
        profile = ROOT / f'rvw/act4-{suffix}/profile.json'
        data, platform, groups = description(profile)
        assert platform.xlen == data['params']['MXLEN'] == 64
        assert {'i', 'm', 'zaamo', 'zalrsc'} <= set(groups)
    supervisor = json.loads((ROOT / 'rvw/act4-64su/profile.json').read_text())
    assert 'sv39' in supervisor['extensions'] and 'sv32' not in supervisor['extensions']
    assert supervisor['params']['PMP_GRANULARITY'] == 4
    assert supervisor['params']['PMP_NA4_SUPPORTED'] is False
    assert selection(ROOT / 'rvw/act4-64su/profile.json')['csr_contract']['missing_required'] == 1
