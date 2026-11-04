"""Conflicting equivalence evidence cannot earn an equivalent mutation verdict."""
import pytest

from rvw.cov.mutation import _classify


@pytest.mark.parametrize('answers', [
    {'eq1': 'PASS', 'eq2': 'FAIL'},
    {'eq1': 'PASS'},
])
def test_all_selected_equivalence_checks_are_required(answers):
    result = {'mutants': [
        {'id': 0, 'mutation': 'mutate -mode none',
         'tests': {'sim': 'PASS', 'eq1': 'PASS', 'eq2': 'PASS'}, 'pending': []},
        {'id': 1, 'mutation': 'mutate -mode inv',
         'tests': {'sim': 'PASS', **answers}, 'pending': []},
    ]}
    _classify(result, ['sim'], ['eq1', 'eq2'])
    assert result['counts']['equivalent'] == 0
    assert result['mutants'][1]['state'] == ('error' if 'eq2' in answers else 'pending')
