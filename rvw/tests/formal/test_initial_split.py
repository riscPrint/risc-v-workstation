from rvw.formal.initial_split import partition_model
import pytest

pytestmark = pytest.mark.fast


def test_partition_keeps_dynamics_and_guards_initial_state_only():
    d = {'modules': {'top': {'netnames': {'count': {'bits': [2, 3]}}, 'cells': {
        'ff': {'type': '$dff', 'connections': {'D': [2, 3], 'Q': [2, 3]}}}}}}
    for value in range(4):
        r = partition_model(d, 'top', 'count', value)
        cells = r['modules']['top']['cells']
        assert cells['ff'] == d['modules']['top']['cells']['ff']
        assert cells['$rvw_split_eq']['connections']['B'] == [str(value & 1), str((value >> 1) & 1)]
        assert cells['$rvw_split_assume']['connections']['EN'] == cells['$rvw_split_init']['connections']['Y']
    assert list(d['modules']['top']['cells']) == ['ff']
    with pytest.raises(ValueError):
        partition_model(d, 'top', 'count', 4)


def test_alias_is_not_a_split_variable():
    d = {'modules': {'top': {'netnames': {'count': {'bits': [2, 2]}}, 'cells': {}}}}
    with pytest.raises(ValueError, match='distinct'):
        partition_model(d, 'top', 'count', 0)


def test_partial_bounded_or_environment_conditioned_results_cannot_pass():
    from rvw.formal.initial_split import case_status
    conditional = {'mode': 'prove', 'status': 'inconclusive', 'winner': {'status': 'pass'}, 'cross_check': 'inconclusive'}
    assert case_status(conditional, 0) == 'pass'  # Known exhaustive partition guard only.
    assert case_status(conditional, 1) == 'inconclusive'
    assert case_status({**conditional, 'mode': 'bmc'}, 0) == 'inconclusive'
    assert case_status({**conditional, 'winner': None}, 0) == 'inconclusive'
    assert case_status({**conditional, 'cross_check': 'disagree'}, 0) == 'inconclusive'
    assert case_status({**conditional, 'status': 'fail', 'winner': {'status': 'fail'}}, 1) == 'fail'
