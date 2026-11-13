"""The production SMP project's declared core and input contract."""
import importlib.util
from pathlib import Path
import tomllib
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT/'examples/smp'
spec = importlib.util.spec_from_file_location('smp_programs', EXAMPLE/'rvw/programs.py')
programs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(programs)


def test_smp_project_loads_with_all_harts():
    data = tomllib.loads((EXAMPLE/'rvw.toml').read_text())
    assert data['core']['configs'] == [f'smp{n}' for n in range(2, 9)]+['serial2','hsm2']
    assert data['core']['default_config'] == 'smp2'
    assert data['core']['lock'] == 'vex-mem'
    assert not data['core']['input_complete']
    assert (EXAMPLE/data['core']['adapter']).is_file()


def test_native_programs_have_per_hart_identity_and_targets():
    for h in range(8):
        source = programs.assembly(h, 'amo')
        assert f'li t0, {h}\nbne a0, t0, fail' in source
        assert f'li s0, {0x81000000+h*64}' in source
    assert 'sd a0, 0(t0)' in programs.assembly(0, 'smoke')
