"""F/D and compressed ACT4 profiles must enable the same ISA in Sail and UDB."""
from pathlib import Path
import json
import pytest
from rvw.regress.act4 import description
pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/fpu'

@pytest.mark.parametrize('width', [32, 64])
def test_act4_fp_and_compressed(width):
    profile, platform, groups = description(ROOT / f'act4-{width}/profile.json')
    assert platform.xlen == width
    assert {'f', 'c', 'zca', 'zcf' if width == 32 else 'zcd'} <= set(groups)
    sail = json.loads((ROOT / f'act4-{width}/sail.json').read_text())
    assert sail['base']['mstatus']['fs_legal_states'] == 'ExtContext_FourState'
    assert sail['extensions']['F']['supported']
    assert sail['extensions']['D']['supported'] == (width == 64)
    assert sail['extensions']['Zca']['supported']
    assert sail['extensions']['Zcf' if width == 32 else 'Zcd']['supported']
    assert profile['params']['MSTATUS_FS_LEGAL_VALUES'] == [0, 1, 2, 3]
