from dataclasses import replace
from rvw.ooo.core import Instruction
from rvw.ooo.rename import elimination, fuses


def test_move_zero_classification():
    move = Instruction('alu', (1,), 2)
    # New instruction metadata is populated by the C2 decoder.
    from types import SimpleNamespace
    op = SimpleNamespace(**{**vars(move), 'encoding': 0x00008113, 'mnemonic': 'addi'})
    assert elimination(op, {'move_elimination': True}) == 'move'
    op.encoding = 0xfff08113
    assert elimination(op, {'move_elimination': True}) is None
    op.mnemonic, op.sources = 'xor', (4, 4)
    assert elimination(op, {'zero_elimination': True}) == 'zero'
    assert elimination(op, {}) is None


def test_fusion_requires_adjacent_matching_register():
    from types import SimpleNamespace
    a = SimpleNamespace(mnemonic='lui', dest=1, pc=0, length=4)
    b = SimpleNamespace(mnemonic='addi', dest=1, sources=(1,), pc=4)
    assert fuses(a, b, {'immediate_fusion': True})
    b.dest = 2
    assert not fuses(a, b, {'immediate_fusion': True})


def test_zero_breaks_dependency_and_move_waits_for_source():
    from rvw.ooo.core import Config, simulate
    c = Config(4, 16, 4, 32, 1, 16, 4, 4, 4, {'alu': 1, 'divide': 12})
    ops = [Instruction('divide', (), 1),
           Instruction('alu', (1, 1), 2, mnemonic='xor'),
           Instruction('alu', (2,), 3)]
    zero = simulate(ops, replace(c, rename={'zero_elimination': True}))
    base = simulate(ops, c)
    assert zero['cycles'] < base['cycles']
    assert zero['events']['issued'] == 2
    assert zero['events']['zero_eliminated'] == 1
    ops[1] = Instruction('alu', (1,), 2, encoding=0x00008113, mnemonic='addi')
    move = simulate(ops, replace(c, rename={'move_elimination': True}))
    assert move['cycles'] >= 15  # The producer is still required.
    assert move['events']['issued'] == 2
    assert move['events']['move_eliminated'] == 1


def test_immediate_fusion_retains_both_retirements():
    from rvw.ooo.core import Config, simulate
    c = Config(4, 16, 4, 32, 1, 16, 4, 4, 4, {'alu': 1})
    ops = [Instruction('alu', (), 1, pc=0, mnemonic='lui'),
           Instruction('alu', (1,), 1, pc=4, mnemonic='addi'),
           Instruction('alu', (1,), 2, pc=8)]
    r = simulate(ops, replace(c, rename={'immediate_fusion': True}))
    assert r['instret'] == 3
    assert r['events']['issued'] == 2
    assert r['events']['fused_immediates'] == 1
    assert r['cycles'] < simulate(ops, c)['cycles']
