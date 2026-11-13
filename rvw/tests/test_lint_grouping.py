"""Repeated register paths retain their locations under a domain-pair finding."""
import pytest
from lint_builder import Builder
from rvw.query.db import run_on
from rvw.lint.structural import analyze

pytestmark = pytest.mark.fast


def test_register_bank_crossings_group_by_effective_reset(tmp_path):
    # Verilog equivalent: four resettable FFs feed four resetless FFs on clk.
    b = Builder(tmp_path / 'bank.db')
    b.domain(1, reset='reset', kind='SYNC')
    for n in range(4):
        b.reg(f's{n}', 1)
        b.reg(f'd{n}', 1, init=None)
        b.edge(f's{n}', f'd{n}')
    r = run_on(b.done(), analyze)
    grouped = [f for f in r['findings'] if f['rule'] == 'rdc.resetless_receiver']
    assert len(grouped) == 1
    assert grouped[0]['count'] == 4
    assert {m['endpoint'] for m in grouped[0]['members']} == {f'd{n}' for n in range(4)}
    assert len(r['rdc']['crossings']) == 4
    assert r['status'] == 'inconclusive'


def test_distinct_clock_pairs_do_not_merge(tmp_path):
    b = Builder(tmp_path / 'clocks.db')
    for n in range(3):
        b.domain(n + 1, clock=f'clk{n}')
        b.reg(f'r{n}', n + 1)
    b.edge('r0', 'r1'); b.edge('r0', 'r2')
    r = run_on(b.done(), analyze)
    assert len([f for f in r['findings'] if f['rule'] == 'cdc.unsynchronized']) == 2
