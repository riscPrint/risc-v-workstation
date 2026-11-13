from dataclasses import replace
import pytest
from rvw.ooo.core import Instruction, simulate
from rvw.ooo.project import configuration
from rvw.ooo.structures import BackwardPredictor
import json
from pathlib import Path
pytestmark = pytest.mark.fast


def test_static_targets_do_not_use_outcome():
    p = BackwardPredictor()
    back = Instruction('branch', pc=0x100, next_pc=0x104, encoding=0xfe000ee3)
    assert p.predict_instruction(back) == 0xfc
    assert p.predict_instruction(replace(back, next_pc=0xfc)) == 0xfc
    forward = replace(back, encoding=0x00000463)
    assert p.predict_instruction(forward) == 0x104
    jump = Instruction('jump', pc=0x100, next_pc=0x104, encoding=0x0080006f, mnemonic='jal')
    assert p.predict_instruction(jump) == 0x108
    assert p.predict_instruction(replace(jump, mnemonic='jalr')) == 0x104


def test_project_static_prediction_changes_misses():
    root = Path(__file__).resolve().parents[2]
    c = configuration(json.loads((root/'examples/vexriscv/rvw/arch/own.json').read_text()))
    ops = [Instruction('branch', pc=0x100, next_pc=0xfc, encoding=0xfe000ee3)]
    assert simulate(ops, c)['events'].get('branch_misses', 0) == 0
    assert simulate(ops, replace(c, branch_prediction='sequential'))['events']['branch_misses'] == 1


def test_compressed_and_negative_jump_targets():
    p = BackwardPredictor()
    assert p.predict_instruction(Instruction('jump', pc=0x100, encoding=0xbffd, mnemonic='c.j', length=2)) == 0xfe
    assert p.predict_instruction(Instruction('jump', pc=0x100, encoding=0xffdff06f, mnemonic='jal')) == 0xfc


def test_static_policy_uses_python_and_refuses_component_predictor():
    from rvw.ooo.native import supported
    from test_ooo import cfg
    c = replace(cfg(), branch_prediction='static_btfn')
    assert not supported(c)
    with pytest.raises(ValueError, match='select static'):
        replace(c, components={'branch': {'model': 'btfn'}})
