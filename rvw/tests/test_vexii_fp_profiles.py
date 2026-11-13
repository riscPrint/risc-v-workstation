"""FP example profile consistency and deterministic program generation."""
import importlib.util
import json
from pathlib import Path
import tomllib
import pytest
from rvw.regress.act4 import description

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv'

@pytest.mark.parametrize('width,config', [(32, 'rv32imafc'), (64, 'rv64imafdc')])
def test_fp_profile(width, config):
    project = tomllib.loads((ROOT / f'rvw{width}fp.toml').read_text())
    assert project['core']['configs'] == [config]
    assert project['core']['jobs'] == 2
    platform = json.loads((ROOT / project['cosim']['platform']).read_text())
    assert platform['isa'] == platform['reference_isa'] == config + '_zicsr_zifencei'
    assert platform['privilege_modes'] == 'M' and platform['pmp_regions'] == 0
    assert not platform.get('csr_masks')
    assert tomllib.loads((ROOT / 'rvw.toml').read_text())['core']['default_config'] == 'rv32im'
