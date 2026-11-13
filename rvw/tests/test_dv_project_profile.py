"""Project platform data determines the native generator profile."""
import importlib.util
import json
from pathlib import Path
import tomllib

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dv_project', ROOT/'scripts/riscv-dv-project.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


@pytest.mark.parametrize('core', ['vexriscv', 'vexiiriscv'])
def test_platform_profile(tmp_path, core):
    source = ROOT/'examples'/core/'rvw/platform.json'
    out = tmp_path/'profile'
    profile.generate(source, out, '~/.cache/rvw/riscv-dv', '~/.cache/rvw/riscv-dv-venv/bin/python')
    settings = tomllib.loads((out/'random.toml').read_text())
    assert settings['target'] == 'rv32imc'
    assert settings['isa'] == json.loads(source.read_text())['isa']
    assert settings['abi'] == 'ilp32'
    assert 'ORIGIN = 0x80000000, LENGTH = 0x1000000' in (out/'link.ld').read_text()
    assert '.tohost' in (out/'link.ld').read_text()
    assert (out/'runtime/user_init.s').read_bytes() == (ROOT/'scripts/riscv-dv/user_init.s').read_bytes()


def test_runtime_defines_scratch_before_gpr_initialization():
    lines = (ROOT/'scripts/riscv-dv/user_init.s').read_text().splitlines()
    instructions = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    assert instructions[0] == 'csrw mscratch, zero'
    assert instructions[1] == 'li x1, 0'

