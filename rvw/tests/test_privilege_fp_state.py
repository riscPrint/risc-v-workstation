import json
from pathlib import Path
import pytest
from rvw.privilege import campaign
from rvw.privilege.fp_state import programs
pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/fpu'

@pytest.mark.parametrize('width', [32, 64])
def test_fp_campaign_selects_machine_slice(width):
    config = campaign.load(ROOT / f'fs{width}.json')
    rows = campaign.scenarios(config)
    assert len(rows) == 2
    assert len(rows[0]['bins']) == 3
    assert '.section .text.init' not in rows[0]['assembly']
    assert 'li t0, 0x4000' in rows[0]['assembly']
    assert 'li t1, 2' in rows[0]['assembly']
    flags = rows[1]
    assert flags['bins'] == ['fp.fs.flags.clean.dirty']
    source = flags['assembly']
    assert 'input: .word 0x7f800001' in source
    assert 'feq.s t1, f1, f1' in source
    assert source.index('csrr t1, mstatus') < source.index('frflags t1')
    assert 'li t0, 16' in source


def test_fp_campaign_refuses_no_f_and_unimplemented_modes():
    with pytest.raises(ValueError):
        programs(dict(isa='rv32im_zicsr'))
    with pytest.raises(ValueError):
        programs(dict(isa='rv64imafdc', modes=['S']))
