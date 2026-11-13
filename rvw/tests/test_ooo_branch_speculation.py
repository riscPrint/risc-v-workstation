from dataclasses import replace
from rvw.ooo.core import Config, Instruction, simulate


def config(**kw):
    return replace(Config(4,32,4,64,4,32,8,8,4,{'alu':1,'branch':8},branch_penalty=10),**kw)


def test_correct_prediction_allows_younger_issue_before_resolution():
    ops = [Instruction('branch',pc=0,next_pc=4)] + [Instruction('alu',pc=4*i) for i in range(1,25)]
    conservative = simulate(ops,config())
    speculative = simulate(ops,config(branch_speculation=True))
    assert speculative['instret'] == conservative['instret'] == 25
    assert speculative['cycles'] < conservative['cycles']
    assert speculative['events']['correct_path_speculative_issues'] > 0


def test_mispredicted_branch_still_pays_recovery():
    ops = [Instruction('branch',pc=0,next_pc=128)] + [Instruction('alu')] * 24
    a = simulate(ops,config())
    b = simulate(ops,config(branch_speculation=True))
    assert a['cycles'] == b['cycles']
    assert b['events']['branch_misses'] == 1
    assert not b['events'].get('correct_path_speculative_issues')


def test_serial_control_still_blocks_speculative_consumers():
    c = replace(config(branch_speculation=True),latencies={'alu':1,'branch':8,'csr':1})
    ops = [Instruction('branch',pc=0,next_pc=4),Instruction('csr'),Instruction('alu')]
    r = simulate(ops,c)
    assert r['events']['control_serialize_blocked'] > 0
    assert r['cycles'] >= 13
