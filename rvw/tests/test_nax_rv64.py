"""RV64 project inputs preserve the RV32 default and bind strict platforms."""
import json
from pathlib import Path
import tomllib
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2] / 'examples/naxriscv'


def test_rv64_configs_and_platforms():
    project = tomllib.loads((ROOT / 'rvw.toml').read_text())
    assert project['core']['default_config'] == 'rv32imasu'
    assert project['suites']['isa']['configs'] == ['rv32imasu']
    for config, modes in [('rv64ima', 'M'), ('rv64imasu', 'MSU')]:
        assert config in project['core']['configs']
        assert config in project['suites']['isa64']['configs']
        platform = json.loads((ROOT / f'rvw/platform-{config}.json').read_text())
        assert platform['xlen'] == 64
        assert platform['privilege_modes'] == modes
        assert platform['isa'] == platform['reference_isa'] == 'rv64ima_zicsr_zifencei'
        assert platform['irq_inputs'] == ([3, 7, 11] if modes == 'M' else [3, 7, 9, 11])
        assert not platform.get('masks')


@pytest.mark.parametrize('value, expected', [(None, 'nax'), ('nax-nax64', 'nax-nax64')])
def test_project_lock_uses_captured_environment(monkeypatch, value, expected):
    from rvw.regress.config import load_config
    if value is None:
        monkeypatch.delenv('RVW_NAX_LOCK', raising=False)
    else:
        monkeypatch.setenv('RVW_NAX_LOCK', value)
    monkeypatch.setenv('RVW_HOME', str(ROOT.parents[1]))
    config = load_config(project=ROOT / 'rvw.toml')
    assert config.lock == expected


def test_supervisor_campaign_has_honest_plan_and_irq_inputs(monkeypatch):
    from rvw.regress.commands.applicability import plan
    features = ROOT / 'rvw/supervisor/features.json'
    result = plan(features, ROOT / 'rvw/supervisor/catalog.json')
    selected = {r['name'] for r in result['suites'] if r['applicable']}
    assert selected == {'mmu-sv39', 'privilege-controls', 'random-privilege-rv64',
                        'scheduled-wfi', 'lrsc-rv64', 'amo-rv64', 'fence-rv64', 'fence-i-rv64'}
    project = tomllib.loads((ROOT / 'rvw64.toml').read_text())
    assert project['core']['default_config'] == 'rv64imasu'
    for cause in (3, 7, 11):
        for enabled in (0, 1):
            options = project['suites'][f'scheduled-wfi-{cause}-{enabled}']['options']
            assert options['probes'] is True
            assert options['irq_schedule'] == f'1:0x0,1000:0x{1 << cause:x},20000:0x0'
