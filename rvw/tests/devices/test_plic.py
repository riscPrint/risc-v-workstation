import pytest
from rvw.cosim.devices import Plic, PlicMap


def model():
    return Plic(PlicMap(0, 0x1000, 0x2000, 0x80, 0x200000, 0x1000, 63, 2))


def test_arbitration_threshold_claim_and_level_gateway():
    p = model()
    for s in (1, 2):
        p.write(s * 4, 3)
        p.set_level(s, True)
    p.write(0x2000, 6)
    p.write(0x2080, 6)
    assert p.irq(0) and p.irq(1)
    p.write(0x200000, 3)
    assert not p.irq(0)
    # Claim ignores threshold, breaks equal priorities by source ID.
    assert p.read(0x200004) == 1
    assert p.read(0x201004) == 2
    assert p.read(0x201004) == 0
    p.write(0x200004, 1)
    assert p.read(0x201004) == 1  # asserted level re-pends on completion
    p.set_level(1, False)
    p.write(0x201004, 1)
    assert p.read(0x201004) == 0


def test_pending_latches_and_changes_are_ordered():
    p = model()
    p.set_level(33, True)
    p.set_level(33, False)
    assert p.read(0x1004) == 2
    p.write(0x2004, 2)
    assert not p.irq(0)  # priority zero
    p.write(33 * 4, 7)
    assert p.irq(0)
    p.write(0x2084, 2)
    assert p.read(0x201004) == 33
    assert not p.irq(0)
    p.write(0x200004, 33)
    assert p.read(0x1004) == 0
    p.write(0, 7)
    p.write(0x2000, 1)
    assert p.read(0) == p.read(0x2000) == 0


def test_reset_and_invalid_access():
    p = model()
    p.set_level(1, True)
    p.write(4, 7)
    p.write(0x2000, 2)
    p.reset()
    assert not p.irq(0) and p.read(0x1000) == p.read(4) == 0
    for a, n in [(3, 4), (0, 8), (0x9000, 4)]:
        with pytest.raises(ValueError):
            p.read(a, n)


def test_spike_plic_oracle(spike_devices):
    p = model()
    actions = [('w', 4, 3), ('w', 8, 3), ('w', 0x2000, 6),
               ('l', 1, 1), ('l', 2, 1), ('r', 0x1000, 0),
               ('r', 0x200004, 0), ('l', 1, 0), ('w', 0x200004, 1),
               ('r', 0x200004, 0), ('l', 2, 0), ('w', 0x200004, 2),
               ('r', 0x200004, 0), ('w', 0x201000, 7),
               ('w', 0x2080, 6), ('l', 1, 1), ('r', 0x1000, 0)]
    expected = []
    for op, a, v in actions:
        value = 0
        if op == 'w':
            p.write(a, v)
        elif op == 'l':
            p.set_level(a, v)
        else:
            value = p.read(a)
        expected.append((1, value, (2048 if p.irq(0) else 0) | (512 if p.irq(1) else 0), 0))
    assert spike_devices('plic', [f'{op} {a} {v} 4' for op, a, v in actions]) == expected


def test_invalid_priority_mask():
    with pytest.raises(ValueError):
        PlicMap(0, 0x1000, 0x2000, 128, 0x200000, 4096, 63, 2, 5)


def test_spike_claim_ignores_threshold(spike_devices):
    # Independent oracle for the controller adapter's threshold conformance case.
    actions = ['w 4 3 4', 'w 8192 2 4', 'w 2097152 3 4',
               'l 1 1 4', 'r 2097156 0 4', 'r 4096 0 4', 'r 2097156 0 4']
    observed = spike_devices('plic', actions)
    assert observed[3] == (1, 0, 0, 0)  # threshold masks both IRQ outputs
    assert observed[4] == (1, 1, 0, 0)  # claim must still return source 1
    assert observed[5:] == [(1, 0, 0, 0), (1, 0, 0, 0)]  # IP clear; no duplicate claim
