"""Restored waves have a new simulator clock and cumulative logical cycles."""
import pytest
from rvw.bundle.clock import wave_clock

pytestmark = pytest.mark.fast


def test_restored_wave_origin_maps_cumulative_cycles():
    clock = wave_clock({'details': {'wave_time_per_cycle': 11,
        'wave_cycle_origin': 1000000, 'wave_time_origin': 58}}, {})
    assert clock.known and clock.t1 < 0
    assert clock.time(1000000) == 58
    assert clock.time(1000001) == 69
    assert clock.cycle(69) == 1000001


@pytest.mark.parametrize('details', [
    {'wave_cycle_origin': -1, 'wave_time_origin': 58},
    {'wave_cycle_origin': 10, 'wave_time_origin': -1},
    {'wave_cycle_origin': '10', 'wave_time_origin': 58},
    {'wave_cycle_origin': 10},
])
def test_bad_restore_origin_is_refused(details):
    with pytest.raises(ValueError, match='restored wave origin'):
        wave_clock({'details': details}, {'period': 11})
