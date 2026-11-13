import copy
from rvw.regress.mmu_memory_effects import check


import pytest

pytestmark = pytest.mark.fast


def plan():
    return [dict(id='a', access='store', address=0x1000, width=4, memory_type='io', data=7),
            dict(id='b', access='load', address=0x1004, width=4, memory_type='io', data=9)]


def test_types_values_replays_and_ordering():
    expected = plan()
    events = [dict(r, kind='bus_effect', sequence=i) for i,r in enumerate(expected)]
    assert check(events, expected, [('a','b')])['status'] == 'consistent'
    assert check(events[:1], expected, [('a','b')])['status'] == 'inconclusive'
    for field, value in [('address',0x2000),('width',8),('memory_type','cached'),('data',8),('access','load')]:
        bad = copy.deepcopy(events)
        bad[0][field] = value
        assert check(bad, expected)['status'] == 'mismatch'
    replay = events + [dict(events[0], sequence=2)]
    assert check(replay, expected)['status'] == 'mismatch'
    swapped = [dict(events[1], sequence=0), dict(events[0], sequence=1)]
    assert check(swapped, expected, [('a','b')])['status'] == 'mismatch'
    assert check(swapped, expected)['status'] == 'consistent'
    assert check(events, [])['status'] == 'inconclusive'


def test_project_protocol_integration(tmp_path):
    import json
    from rvw.regress.mmu_protocol import configured_check
    path = tmp_path / 'probes.json'
    raw = dict(schema='rvw.mmu-probes/1', harts=[0], probes=dict(bus_effect='project.device.effects'), transactions=plan(), ordering=[['a','b']])
    path.write_text(json.dumps(raw))
    events = [dict(r, kind='bus_effect', cycle=i, sequence=i) for i,r in enumerate(plan())]
    result = configured_check(events, path)
    assert result['memory_effects']['status'] == 'consistent'
    assert result['status'] == 'inconclusive'  # No TLB/atomicity evidence.
    events[0]['memory_type'] = 'cached'
    assert configured_check(events, path)['status'] == 'mismatch'
