import pytest
from rvw.formal.ic3_lemmas import candidates, expression, inject

pytestmark = pytest.mark.fast


def test_map_pdr_cubes_and_skip_auxiliary_state():
    pla = '# PDR invariant\n.i 3\n.o 1\n.p 2\n.ilb lo0 lo1 lo3\n.ob inv\n--1 1\n11- 1\n.e\n'
    rows, skipped = candidates(pla, 'input 0 0 clk\nlatch 0 0 count\nlatch 1 1 count\n')
    assert skipped == 1 and len(rows) == 1
    assert rows[0]['expression'] == "!((count[0] == 1'b1) && (count[1] == 1'b1))"
    assert inject('module top;\nendmodule\n', rows).count('always @* assert') == 1
    # Do not assume that an inverted initial-state encoding is a direct RTL bit.
    assert candidates('.i 1\n.o 1\n.p 1\n.ilb lo0\n.ob inv\n1 1\n.e\n', 'invlatch 0 0 count\n') == ([], 1)


def test_incomplete_exports_and_invalid_literals_are_refused():
    with pytest.raises(ValueError, match='incomplete'):
        candidates('.i 1\n.o 1\n.p 2\n.ilb lo0\n.ob inv\n1 1\n.e\n', '')
    with pytest.raises(ValueError, match='columns'):
        candidates('.i 1\n.o 1\n.p 1\n.ilb x0\n1 1\n.e\n', '')
    with pytest.raises(ValueError, match='invalid'):
        expression({'literals': [{'signal': 'q); bad', 'bit': 0, 'value': 1}]})


def test_empty_invariant_does_not_invent_a_predicate():
    assert candidates('.i 0\n.o 1\n.p 0\n.ilb\n.ob inv\n.e\n', '') == ([], 0)


def test_command_registration():
    from rvw.cli import build_parser
    from rvw.formal.commands.ic3_lemmas import mcp_tools
    args = build_parser().parse_args(['formal', 'ic3-lemmas', '--manifest', 'plan.json', '--out', 'out'])
    assert args.library is None
    assert [t.name for t in mcp_tools()] == ['formal_ic3_lemmas']
