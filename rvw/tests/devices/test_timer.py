import json
from pathlib import Path
import pytest
from rvw.cosim.devices import Timer, TimerMap, Plic, PlicMap

ROOT = Path(__file__).resolve().parents[3]


def model():
    return Timer(TimerMap(0xbff8, (0x4000, 0x4008), (0, 4), 0, 0))


def test_split_writes_boundary_software_and_wrap():
    t = model()
    assert t.irq(0) == 128
    t.write(0x4000, 0xffffffff)
    t.write(0x4004, 1)
    t.write(0x4000, 5)
    t.write(0xbff8, (1 << 32) + 4, 8)
    assert t.irq(0) == 0
    t.tick()
    assert t.irq(0) == 128
    t.write(4, 3)
    assert t.irq(1) == 136 and t.irq(0) == 128
    t.write(4, 2)
    assert t.irq(1) == 128
    t.write(0xbff8, t.MASK, 8)
    t.tick()
    assert t.mtime == 0 and t.irq(0) == 0


def test_relocated_aclint_and_project_data():
    # ACLINT MSWI and MTIMER can be disjoint. Hart IDs need not set addresses.
    t = Timer(TimerMap(0x18000, (0x10000, 0x10008), (0x30000, 0x30004), 7, 20))
    t.write(0x30004, 1)
    assert t.irq(1) == 8
    t.tick(13)
    assert t.irq(0) == 128 and t.irq(1) == 136
    for core in ['boom', 'vexriscv']:
        data = json.loads((ROOT / f'examples/{core}/devices.json').read_text())
        declared = Timer(TimerMap.from_dict(data['timer']))
        assert declared.read(declared.map.mtime, 8) == 0
        plic = Plic(PlicMap(**data['plic']))
        plic.write(plic.map.priority + 4, 7)
        plic.write(plic.map.enable, 2)
        plic.set_level(1, True)
        assert plic.irq(0)


def test_reset_and_bad_accesses():
    t = model()
    t.write(0, 1)
    t.tick(12)
    t.write(0x4000, 10, 8)
    t.reset()
    assert t.software == [0, 0] and t.compare == [0, 0] and t.mtime == 0
    for address, size in [(0, 8), (0x4002, 4), (0x1234, 4), (0, 1)]:
        with pytest.raises(ValueError):
            t.read(address, size)
    with pytest.raises(ValueError):
        t.tick(-1)


def test_spike_clint_oracle(spike_devices):
    t = model()
    actions = [('r', 0xbff8, 0, 8), ('w', 0x4000, 0xffffffff, 4),
               ('w', 0x4004, 1, 4), ('w', 0x4000, 5, 4),
               ('w', 0xbff8, (1 << 32) + 4, 8), ('t', 1, 0, 4),
               ('r', 0xbffc, 0, 4), ('w', 4, 1, 4), ('r', 4, 0, 4),
               ('w', 4, 0, 4), ('w', 0x4008, 0xffffffffffffffff, 8)]
    expected = []
    for op, a, v, n in actions:
        result = 0
        if op == 'r':
            result = t.read(a, n)
        elif op == 'w':
            t.write(a, v, n)
        else:
            t.tick(a)
        expected.append((1, result, t.irq(0), t.irq(1)))
    assert spike_devices('clint', [f'{op} {a} {v} {n}' for op, a, v, n in actions]) == expected
