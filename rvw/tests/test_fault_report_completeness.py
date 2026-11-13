"""Reports retain planned faults when campaign output is incomplete."""
import pytest

from rvw.fault.campaign import plan, report

pytestmark = pytest.mark.fast


@pytest.fixture
def campaign():
    data = plan([dict(path='pipeline.state', width=2)], kinds=('flip',),
                window=(1, 2), samples=2)
    outcomes = [dict(fault, classification='safe', evidence={}) for fault in data['faults']]
    return data, outcomes


def test_missing_outcome_remains_in_the_denominator(campaign):
    data, outcomes = campaign
    result = report(data, outcomes[:1])
    assert result['planned'] == 2
    assert result['counts']['safe'] == 1
    assert result['counts']['inconclusive'] == 1
    assert result['unresolved'] == [outcomes[1]['id']]
    assert result['safe_fraction'] == 1.0  # Fraction of confirmed injections only.


def test_no_outcomes_does_not_erase_the_plan(campaign):
    data, outcomes = campaign
    result = report(data, [])
    assert result['planned'] == 2
    assert result['injected'] == 0
    assert result['unresolved'] == [o['id'] for o in outcomes]


@pytest.mark.parametrize('change', ['duplicate', 'unknown', 'wrong_bit'])
def test_conflicting_outcome_identity_is_rejected(campaign, change):
    data, outcomes = campaign
    if change == 'duplicate':
        outcomes.append(dict(outcomes[0]))
    elif change == 'unknown':
        outcomes[0]['id'] = 'not-in-plan'
    else:
        outcomes[0]['bit'] += 1
    with pytest.raises(ValueError):
        report(data, outcomes)
