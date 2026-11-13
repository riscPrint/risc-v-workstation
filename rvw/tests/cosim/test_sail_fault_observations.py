"""Fault completion bytes come from the reference memory log, never the DUT."""
import pytest
from rvw.cosim.fault import observed_fault
from rvw.cosim.sail import parse
from test_state import fault_fixture, run


def effect():
    return dict(insn=0x0020a023, trap=1, intr=0, cause=7,
                before=[0, 0x80000002] + [0] * 30, mem_rmask=0, mem_wmask=0)


def test_independent_partial_store():
    observation = observed_fault(effect(), {'r': [], 'w': [(0x90000002, 2, 0x1234)]}, 64)
    assert observation == dict(addr=0x80000002, rmask=0, wmask=15,
        completed_rmask=0, completed_wmask=3, rdata=None, wdata=0x1234)


@pytest.mark.parametrize('fragments', [[(0x90000001, 1, 0)], [(0x90000005, 2, 0)],
                                       [(0x90000002, 2, 0), (0x90000003, 1, 0)]])
def test_bad_partial_fragments(fragments):
    with pytest.raises(ValueError, match='fragment'):
        observed_fault(effect(), {'r': [], 'w': fragments}, 64)


def test_split_page_effects_are_not_guessed():
    e = effect()
    e['before'][1] = 0x80000fff
    with pytest.raises(ValueError, match='translation'):
        observed_fault(e, {'r': [], 'w': []}, 64)


def test_partial_effect_comparison(tmp_path):
    header, row, model = fault_fixture()
    model.name = 'sail'
    observed = dict(addr=0, rmask=15, wmask=0, completed_rmask=3,
                    completed_wmask=0, rdata=0x1234, wdata=None)
    model.fault_access = lambda effect: observed
    row['fault_access'].update(completed_rmask=3, rdata='0x1234')
    assert run(tmp_path, row, model, header)['status'] == 'match'
    row['fault_access']['rdata'] = '0x1235'
    assert 'fault_access.rdata' in run(tmp_path, row, model, header)['mismatch']['differences']


def test_sail_parser_observes_zero_completion():
    rows = list(parse('''[0] [M]: 0x80000000 (0x00100093) addi x1, x0, 1
x1 <- 0x1

[1] [M]: 0x80000004 (0x0000a103) lw x2, 0(x1)
handling exc#misaligned-load tval=0x1
CSR mepc (0x341) <- 0x80000004

[2] [M]: 0x80000100 (0x00000013) nop
'''.splitlines()))
    assert rows[1]['fault_access']['addr'] == 1
    assert rows[1]['fault_access']['rmask'] == 15
    assert rows[1]['fault_access']['completed_rmask'] == 0
    assert rows[1]['fault_access']['rdata'] is None
