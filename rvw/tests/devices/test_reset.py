"""Fixtures for the observer, and actual reset calls on the reference devices.

These tests do not substitute for an RTL reset pulse.
"""
import pytest
from rvw.cosim.reset import ResetContract, ResetSample, check_reset
from rvw.cosim.devices import Plic, PlicMap, Timer, TimerMap


@pytest.mark.parametrize('kind', ['cold', 'warm', 'local', 'activity'])
def test_declared_reset_contract(kind):
    # Warm/local retained state is a project choice, not a generic RISC-V rule.
    expected = 0x55 if kind in ('warm', 'local') else 0
    contract = ResetContract({'pc': (0x80000000, 0xffffffff), 'retained': (expected, 255)}, ('bus', 'trap', 'debug'))
    samples = [ResetSample(10, True, {}, dict(bus=False, trap=False, debug=False)),
               ResetSample(12, False, {'pc': 0x80000000, 'retained': expected}, {})]
    assert check_reset(contract, samples)['status'] == 'consistent'
    bad_state = samples[:-1] + [ResetSample(12, False, {'pc': 0x80000004, 'retained': expected}, {})]
    assert check_reset(contract, bad_state)['status'] == 'mismatch'
    bad_valid = [ResetSample(10, True, {}, dict(bus=True, trap=False, debug=False)), samples[-1]]
    assert check_reset(contract, bad_valid)['status'] == 'mismatch'


def test_missing_reset_evidence_is_inconclusive():
    contract = ResetContract({'pc': (0, 255)}, ('bus',))
    assert check_reset(contract, [])['status'] == 'inconclusive'
    initialized = [ResetSample(0, False, {'pc': 0}, {'bus': False})]
    assert check_reset(contract, initialized)['status'] == 'inconclusive'
    unknown = [ResetSample(1, True, {}, {}), ResetSample(2, False, {}, {})]
    assert check_reset(contract, unknown)['status'] == 'inconclusive'
    with pytest.raises(ValueError):
        check_reset(contract, [ResetSample(2, True, {}, {}), ResetSample(1, False, {}, {})])


def test_repeated_reference_reset_during_device_activity():
    timer = Timer(TimerMap(0xbff8, (0x4000,), (0,), 0, (1 << 64)-1))
    plic = Plic(PlicMap(0, 0x1000, 0x2000, 128, 0x200000, 4096, 63, 1))
    for _ in range(3):
        timer.write(0, 1)
        timer.tick(100)
        timer.write(0x4000, 50, 8)
        plic.write(4, 3)
        plic.write(0x2000, 2)
        plic.set_level(1, True)
        assert timer.irq(0) == 136 and plic.irq(0)
        assert plic.read(0x200004) == 1  # outstanding claim at reset
        timer.reset()
        plic.reset()
        assert timer.mtime == timer.software[0] == 0 and timer.irq(0) == 0
        assert plic.read(0x1000) == plic.read(4) == plic.read(0x2000) == 0
        assert not plic.busy and not plic.irq(0)
        plic.write(0x200004, 1)  # stale completion after reset has no effect
        assert not plic.busy
