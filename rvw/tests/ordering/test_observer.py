import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('ordering_observer',
    Path(__file__).resolve().parents[3] / 'RiscvSim/tests/ordering/observer.py')
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


@pytest.mark.parametrize('pred', list('rwio'))
@pytest.mark.parametrize('succ', list('rwio'))
def test_order_and_swapped_negative(pred, succ):
    plan = {'boundary': 'device-visible', 'edges': [['a', 'b']]}
    observation = {'boundary': 'device-visible', 'independent': True, 'complete': True,
        'events': [{'id': 'a', 'class': pred, 'issue': 1, 'complete': 3},
                   {'id': 'b', 'class': succ, 'issue': 4, 'complete': 7}]}
    assert observer.check(plan, observation)['status'] == 'consistent'
    observation['events'][1]['issue'] = 2
    assert observer.check(plan, observation)['status'] == 'mismatch'


@pytest.mark.parametrize('change', ['missing', 'empty', 'dependent', 'incomplete', 'boundary', 'duplicate', 'badtime'])
def test_insufficient_evidence(change):
    plan = {'boundary': 'bus', 'edges': [['a', 'b']]}
    observation = {'boundary': 'bus', 'independent': True, 'complete': True,
        'events': [{'id': 'a', 'class': 'w', 'issue': 1, 'complete': 2},
                   {'id': 'b', 'class': 'r', 'issue': 3, 'complete': 4}]}
    if change == 'missing': observation['events'].pop()
    if change == 'empty': plan['edges'] = []
    if change == 'dependent': observation['independent'] = False
    if change == 'incomplete': observation['complete'] = False
    if change == 'boundary': observation['boundary'] = 'retire'
    if change == 'duplicate': observation['events'][1]['id'] = 'a'
    if change == 'badtime': observation['events'][1]['issue'] = True
    assert observer.check(plan, observation)['status'] == 'inconclusive'
