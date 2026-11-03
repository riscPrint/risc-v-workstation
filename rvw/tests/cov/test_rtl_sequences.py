import pytest
from rvw.cov.rtl import sample, validate
from .test_rtl import plan, write  # fixture


def sequence(plan, steps=None):
    plan['sequences'] = [{'id': 'start-finish', 'domain': 'structural', 'steps': steps or [
        {'when': {'TOP.state': [0]}}, {'when': {'TOP.state': [2]}, 'delay': [1, 2]}]}]


def test_activation_completion_overlap_and_reset(tmp_path, plan):
    sequence(plan)
    config, trace = write(tmp_path, plan, [(0, 0), (0, 0), (0, 2), (0, 0), (1, 2), (0, 0)])
    stats = sample(config, [trace])['sequences'][0]
    assert [stats[k] for k in ('activated', 'completed', 'expired', 'reset_cancelled', 'pending')] == [4, 2, 0, 1, 1]


def test_expiry_and_no_cross_run_sequences(tmp_path, plan):
    sequence(plan)
    config, a = write(tmp_path, plan, [(0, 0), (0, 1), (0, 1), (0, 2), (0, 0)], 'a')
    _, b = write(tmp_path, plan, [(0, 2)], 'b')
    stats = sample(config, [a, b])['sequences'][0]
    assert stats['activated'] == 2 and stats['expired'] == 1
    assert stats['completed'] == 0 and stats['pending'] == 1


def test_three_step_first_match_advancement(tmp_path, plan):
    sequence(plan, [{'when': {'TOP.state': [0]}}, {'when': {'TOP.state': [1]}, 'delay': [1, 3]},
                    {'when': {'TOP.state': [2]}, 'delay': [2, 2]}])
    config, trace = write(tmp_path, plan, [(0, 0), (0, 1), (0, 2), (0, 2)])
    stats = sample(config, [trace])['sequences'][0]
    assert stats['activated'] == stats['completed'] == 1


@pytest.mark.parametrize('delay', [[0, 1], [2, 1], [1, 1000001], 'unbounded', [1.0, 2]])
def test_unsupported_delays_refuse(plan, delay):
    sequence(plan)
    plan['sequences'][0]['steps'][1]['delay'] = delay
    with pytest.raises(ValueError):
        validate(plan)
