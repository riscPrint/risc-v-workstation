from dataclasses import replace
import pytest
from rvw.ooo.core import Config, Instruction, simulate

pytestmark = pytest.mark.fast


def config(**kwargs):
    return Config(2, 8, 2, 16, 2, 8, 2, 2, 2,
                  dict(alu=1, branch=10, load=2, store=2), **kwargs)


def test_mix_occupancy_is_bounded_and_squashed():
    ops = [Instruction('branch', pc=0, next_pc=100)] + [
        Instruction('load', address=128, size=4, pc=100+4*i, next_pc=104+4*i) for i in range(10)]
    result = simulate(ops, config(wrong_path_occupancy=True), backend='python')
    assert result['instret'] == len(ops)
    assert result['events']['wrong_path_renamed'] > 0
    assert result['events']['wrong_path_squashed'] == result['events']['wrong_path_renamed']
    assert result['max_occupancy']['load_entries'] <= 2
    assert result['max_occupancy']['rob_entries'] <= 16
    assert result['events'].get('wrong_path_load_requests', 0) == 0


def test_wrong_occupancy_flag_is_boolean():
    with pytest.raises(ValueError, match='wrong_path_occupancy'):
        config(wrong_path_occupancy=1)


def test_wrong_path_allocates_while_branch_waits_for_operand():
    ops = [Instruction('load', dest=1, address=128, size=4),
           Instruction('branch', sources=(1,), pc=4, next_pc=100),
           Instruction('alu', pc=100, next_pc=104)]
    c = replace(config(wrong_path_occupancy=True), latencies=dict(alu=1, branch=2, load=20, store=2))
    result = simulate(ops, c, backend='python')
    # A two-cycle branch alone cannot admit this many operations. Its operand
    # wait must also contribute speculative queue occupancy.
    assert result['events']['wrong_path_renamed'] > c.fetch_width * c.latencies['branch']
    assert result['events']['wrong_path_squashed'] == result['events']['wrong_path_renamed']


def test_prediction_ticket_survives_multiple_renamed_branches():
    class Predictor:
        def __init__(self): self.pending = None; self.last_delay = 0; self.updated = []
        def predict_instruction(self, op):
            self.pending = op.pc
            return op.next_pc
        def update_instruction(self, op):
            assert self.pending == op.pc
            self.updated.append(op.pc)
            self.pending = None
    ops = [Instruction('branch', pc=i*4, next_pc=i*4+4) for i in range(8)]
    predictor = Predictor()
    result = simulate(ops, config(wrong_path_occupancy=True, branch_speculation=True), backend='python', predictor=predictor)
    assert result['instret'] == 8
    assert predictor.updated == [i*4 for i in range(8)]


def test_correct_predictions_do_not_add_a_fetch_guard():
    ops = [Instruction('branch', pc=4*i, next_pc=4*i+4) for i in range(12)]
    c = config(branch_speculation=True, frontend=dict(decode_width=2, decode_entries=8, decode_latency=2, fetch_latency=3))
    original = simulate(ops, c, backend='python')
    occupancy = simulate(ops, replace(c, wrong_path_occupancy=True), backend='python')
    assert occupancy['cycles'] <= original['cycles']
    assert occupancy['events'].get('wrong_path_renamed', 0) == 0
