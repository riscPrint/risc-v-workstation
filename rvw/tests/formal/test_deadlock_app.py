import pytest
from rvw.formal.deadlock_app import check


def model():
    return dict(states=['idle','wait','done','trap'],initial=['idle'],progress=['done'],edges=[['idle','wait'],['wait','done'],['done','idle'],['trap','trap']])


def test_unreachable_dead_region_is_not_failure():
    result=check(model())
    assert result['status']=='pass'
    assert 'trap' not in result['reachable']


def test_reachable_no_progress_region_fails():
    m=model();m['edges'].append(['wait','trap'])
    result=check(m)
    assert result['status']=='fail'
    assert result['progress_impossible']==['trap']


def test_can_wait_forever_but_progress_remains_possible():
    m=model();m['edges'].append(['wait','wait'])
    assert check(m)['status']=='pass'


def test_fairness_impossible_is_inconclusive():
    m=model();m['fairness']=[['trap']]
    assert check(m)['status']=='inconclusive'


def test_fair_nonprogress_component_fails():
    m=model();m['edges'].append(['wait','trap']);m['fairness']=[['idle','trap']]
    assert check(m)['status']=='fail'


def test_unknown_endpoints_fail_closed():
    m=model();m['edges'].append(['idle','unknown'])
    with pytest.raises(ValueError,match='unknown transition'):
        check(m)
