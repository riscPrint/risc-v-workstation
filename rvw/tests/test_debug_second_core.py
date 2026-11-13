"""Project data for the second debug target stays outside generic code."""
from pathlib import Path
import json
import pytest
from rvw.debug.profile import load

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('transport', ['dmi', 'jtag'])
def test_vexii_profile_has_explicit_endpoint(transport):
    folder = ROOT / 'examples/vexiiriscv/rvw/debug'
    p = load(folder / f'profile-{transport}.toml')
    assert p['transport_declared']
    assert p['transport']['kind'] == {'dmi': 'dmi_process', 'jtag': 'remote_bitbang'}[transport]
    assert p['triggers']['count'] == 2
    pins = json.loads((folder / 'binding.json').read_text())
    assert pins['schema'] == 'rvw.debug-binding/1'
    assert pins['dmi']['abits'] == 7


def test_debug_configs_preserve_project_default():
    import tomllib
    project = tomllib.loads((ROOT / 'examples/vexiiriscv/rvw.toml').read_text())
    assert project['core']['default_config'] == 'rv32im'
    assert project['core']['configs'][0] == 'rv32im'
    assert {'rv32im_dmi', 'rv32im_jtag'} <= set(project['core']['configs'])


def test_reset_check_requires_a_nonzero_initial_data_value():
    from types import SimpleNamespace
    from rvw.debug.checks import dmactive_reset
    from rvw.debug.suite import Fail
    ctx = SimpleNamespace(write=lambda *args: None, read=lambda addr: 0,
                          p={'datacount': 1, 'abstract': ['gpr']}, require=lambda *args: None,
                          set_gpr=lambda *args: None, gpr=lambda reg: 0,
                          activate=lambda: None, observe=lambda *args: None)
    with pytest.raises(Fail, match='DATA0 seed GPR did not read back'):
        dmactive_reset(ctx)


def test_data_readback_detects_a_stale_read_mirror():
    from types import SimpleNamespace
    from rvw.debug.checks import data_readback
    from rvw.debug.suite import Fail
    ctx = SimpleNamespace(p={'datacount': 1}, require=lambda *args: None,
                          write=lambda *args: None, read=lambda addr: 0)
    with pytest.raises(Fail, match='DATA0 read 0x0'):
        data_readback(ctx)
