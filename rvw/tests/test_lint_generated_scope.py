"""Source-scoped temporary assignments do not prove a latch in lowered RTL."""
import pytest
from lint_builder import Builder
from rvw.lint.rules import analyze
from rvw.query.db import run_on

pytestmark = pytest.mark.fast


def test_generated_expression_latch_is_unresolved_not_certified(tmp_path):
    b = Builder(tmp_path / 'design.db')
    b.sig('temporary', width=8)
    b.c.execute('UPDATE signals SET generated=1 WHERE id=?', (b.ids['temporary'],))
    b.assign('temporary', ' := Operator$UInt$ShiftLeftByUInt[8](one,tail)', cond=1)
    result = run_on(b.done(), analyze)
    assert result['status'] == 'inconclusive'
    assert result['unresolved'][0]['endpoint'] == 'temporary'
    assert 'source-scope' in result['unresolved'][0]['reason']
    assert not any(row['rule'] == 'lint.latch' for row in result['findings'])


def test_named_conditional_assignment_keeps_latch_finding(tmp_path):
    b = Builder(tmp_path / 'design.db')
    b.sig('held', width=8)
    b.assign('held', ' := input', cond=1)
    result = run_on(b.done(), analyze)
    assert any(row['rule'] == 'lint.latch' for row in result['findings'])
    assert not result['unresolved']
