"""Paired endpoint fixtures, not DUT transaction evidence."""
from copy import deepcopy

import pytest

from rvw.soc.bridge import compare


def inputs():
    t = dict(bridge='reg', software_address=0x1000, bus_address=0, size=4, write=True,
             data=0x12345678, error=False,
             beats=[dict(address=0, data=0x5678, mask=3, error=False, write=True),
                    dict(address=2, data=0x1234, mask=3, error=False, write=True)])
    bridge = dict(data_bytes=2, byteorder='little', software_byteorder='little')
    region = dict(base=0x1000, registers=[dict(offset=0, width=32, access='rw',
                  read_action='clear', write_action='one_to_clear')])
    return t, bridge, region


def checked(t, b, r):
    checks = {}
    compare(t, b, r, lambda name, actual, expected: checks.update({name: actual == expected}), 'access')
    return checks


def test_split_width_and_endianness():
    t, b, r = inputs()
    assert all(checked(t, b, r).values())
    b['byteorder'] = 'big'
    assert not all(checked(t, b, r).values())
    t['beats'][0]['data'] = 0x7856
    t['beats'][1]['data'] = 0x3412
    assert all(checked(t, b, r).values())
    b['software_byteorder'] = 'big'
    assert not all(checked(t, b, r).values())


@pytest.mark.parametrize('change', [
    lambda t: t['beats'][1].update(address=0),
    lambda t: t['beats'][0].update(mask=1),
    lambda t: t['beats'][0].update(data=0),
    lambda t: t['beats'][1].update(error=True),
    lambda t: t['beats'][1].update(write=False),
    lambda t: t.update(error=True),
])
def test_negative_endpoint_observations(change):
    t, b, r = inputs()
    change(t)
    assert not all(checked(t, b, r).values())


def test_error_propagation_and_no_side_effect():
    t, b, r = inputs()
    t.update(error=True, register=dict(before=255, after=255))
    t['beats'][0]['error'] = True
    assert all(checked(t, b, r).values())
    t['register']['after'] = 0
    assert not all(checked(t, b, r).values())


@pytest.mark.parametrize('write,action,expected', [(True, 'one_to_clear', 0xff & ~0x12345678),
                                                 (True, 'normal', 0x12345678),
                                                 (False, 'clear', 0), (False, 'none', 0x12345678)])
def test_register_effects(write, action, expected):
    t, b, r = inputs()
    t['write'] = write
    for beat in t['beats']:
        beat['write'] = write
    reg = r['registers'][0]
    reg['write_action' if write else 'read_action'] = action
    t['register'] = dict(before=255 if write else t['data'], after=expected)
    assert all(checked(t, b, r).values())
    t['register']['after'] ^= 1
    assert not all(checked(t, b, r).values())


@pytest.mark.parametrize('change', [lambda t: t.update(size=0), lambda t: t.update(size=65),
    lambda t: t['beats'][0].update(mask=4), lambda t: t['beats'][0].update(address=1),
    lambda t: t['beats'][0].update(data=0x10000), lambda t: t.update(beats=[]),
    lambda t: t.update(register=dict(before=0, after=0), software_address=0x1001)])
def test_refuse_unsupported(change):
    t, b, r = inputs()
    change(t)
    with pytest.raises(ValueError):
        checked(t, b, r)


@pytest.mark.parametrize('error', [False, True])
@pytest.mark.parametrize('action', ['normal', 'one_to_clear'])
def test_hardware_updates_and_masked_writes(error, action):
    t, b, r = inputs()
    t['error'] = error
    for beat in t['beats']:
        beat['error'] = error
    r['registers'][0]['write_action'] = action
    before, mask, clear, set_bits = 0xFF, 0xF, 0x80, 0x88
    software = before if error else (before & ~(t['data'] & mask) if action == 'one_to_clear'
                                     else (before & ~mask) | (t['data'] & mask))
    target = (software & ~clear) | set_bits
    t['register'] = dict(before=before, after=target, write_mask=mask, hw_clear=clear, hw_set=set_bits)
    assert all(checked(t, b, r).values())
    t['register']['after'] ^= 1
    assert not all(checked(t, b, r).values())


def test_hardware_set_wins_read_clear():
    t, b, r = inputs()
    t['write'] = False
    for beat in t['beats']:
        beat['write'] = False
    t['register'] = dict(before=t['data'], after=3, hw_set=3)
    assert all(checked(t, b, r).values())
    t['register']['after'] = 0
    assert not all(checked(t, b, r).values())


@pytest.mark.parametrize('key', ['write_mask', 'hw_clear', 'hw_set'])
def test_reject_hardware_observation_width(key):
    t, b, r = inputs()
    t['register'] = dict(before=0, after=0)
    t['register'][key] = 1 << 32
    with pytest.raises(ValueError):
        checked(t, b, r)
