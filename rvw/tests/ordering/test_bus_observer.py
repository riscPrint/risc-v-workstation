import copy
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3] / 'RiscvSim/tests/ordering'
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('bus_observer', ROOT / 'bus_observer.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
sys.path.pop(0)


def sample():
    plan = {'boundary': 'accepted-external-tilelink', 'edges': [['output', 'input']],
            'accesses': [{'id': 'output', 'class': 'o', 'address': '0xc000000', 'opcode': 0, 'size_log2': 2, 'data': '0x7', 'mask': '0xf'},
                         {'id': 'input', 'class': 'i', 'address': '0xc000008', 'opcode': 4, 'size_log2': 2, 'expected_read_data': '0x9'}]}
    rows = [{'schema': 'rvw.bus-observations/1', 'boundary': plan['boundary'], 'independent': True, 'bus_bytes': 8},
            {'channel': 'a', 'cycle': '1', 'sequence': '0', 'source': '0x0', 'address': '0xc000000', 'opcode': 0, 'size_log2': 2, 'data': '0x7', 'mask': '0xf'},
            {'channel': 'd', 'cycle': '3', 'sequence': '1', 'source': '0x0', 'opcode': 0, 'size_log2': 2, 'denied': False, 'data': '0x0'},
            {'channel': 'a', 'cycle': '4', 'sequence': '2', 'source': '0x0', 'address': '0xc000008', 'opcode': 4, 'size_log2': 2, 'mask': '0xf'},
            {'channel': 'd', 'cycle': '5', 'sequence': '3', 'source': '0x0', 'opcode': 1, 'size_log2': 2, 'denied': False, 'data': '0x9'},
            {'kind': 'end', 'cycle': '6', 'status': 'pass'}]
    return plan, rows


def test_independent_device_edges():
    plan, rows = sample()
    observation = m.observe(plan, rows)
    assert observation['complete']
    assert m.check(plan, observation)['status'] == 'consistent'
    plan['edges'] = [['input', 'output']]
    assert m.check(plan, m.observe(plan, rows))['status'] == 'mismatch'


@pytest.mark.parametrize('fault', ['denied', 'missing', 'truncated', 'data', 'mask', 'response', 'sequence', 'duplicate', 'terminal', 'multibeat'])
def test_missing_or_bad_bus_evidence(fault):
    plan, rows = sample()
    if fault == 'denied': rows[2]['denied'] = True
    if fault == 'missing': rows[3]['address'] = '0xc000010'
    if fault == 'truncated': rows.pop()
    if fault == 'data': rows[4]['data'] = '0xa'
    if fault == 'mask': rows[1]['mask'] = '0x1'
    if fault == 'response': rows[4]['opcode'] = 0
    if fault == 'sequence': rows[2]['sequence'] = '4'
    if fault == 'duplicate': plan['accesses'].append(copy.deepcopy(plan['accesses'][0]))
    if fault == 'terminal': rows[-1]['status'] = 'timeout'
    if fault == 'multibeat': plan['accesses'][0]['size_log2'] = 4
    observation = m.observe(plan, rows)
    assert not observation['complete']
    assert m.check(plan, observation)['status'] == 'inconclusive'


def test_coherent_channels_and_same_edge_source_reuse():
    plan, rows = sample()
    rows[3]['cycle'] = '3'  # New A appears before old D in capture order.
    rows[2], rows[3] = rows[3], rows[2]
    rows.insert(3, {'channel': 'e', 'cycle': '3', 'sink': '0x2'})
    for seq, row in enumerate(rows[1:-1]):
        row['sequence'] = str(seq)
    observation = m.observe(plan, rows)
    assert observation['complete']
    assert m.check(plan, observation)['status'] == 'consistent'


def test_zero_latency_response_on_request_edge():
    plan, rows = sample()
    rows[2]['cycle'] = '1'
    assert m.observe(plan, rows)['complete']


def test_native_campaign_plans_all_io_pairs_at_the_declared_pma_boundary():
    sys.path.insert(0, str(ROOT))
    try:
        spec = importlib.util.spec_from_file_location('fence_device', ROOT.parents[1] / 'boom/tests/fence-device.py')
        device = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(device)
    finally:
        sys.path.pop(0)
    source, plan = device.campaign()
    accesses = {a['id']: a for a in plan['accesses']}
    assert {(accesses[a]['class'], accesses[b]['class']) for a, b in plan['edges']} == set(__import__('itertools').product('io', repeat=2))
    assert len({a['address'] for a in accesses.values()}) == 8
    assert all(0xc000100 <= int(a['address'], 0) < 0xc001000 for a in accesses.values())
    assert source.count(' fence ') == 5
    assert 'fence iorw, iorw' in source


def test_unselected_bus_lanes_do_not_define_write_or_read_bytes():
    plan, rows = sample()
    # BOOM replicates a 32-bit store across its 64-bit data bus. Only mask lanes count.
    rows[1]['data'] = '0x700000007'
    rows[4]['data'] = '0xdeadbeef00000009'
    assert m.observe(plan, rows)['complete']
    rows[1]['data'] = '0x700000008'
    assert not m.observe(plan, rows)['complete']


@pytest.mark.parametrize('fault', ['empty-write', 'wrong-write-lanes', 'partial-get', 'misaligned'])
def test_illegal_request_cannot_establish_planned_access(fault):
    plan, rows = sample()
    plan['accesses'][0].pop('mask')
    rows[3]['mask'] = '0xf'
    if fault == 'empty-write': rows[1]['mask'] = '0x0'
    if fault == 'wrong-write-lanes': rows[1]['mask'] = '0xf0'
    if fault == 'partial-get': rows[3]['mask'] = '0x1'
    if fault == 'misaligned':
        plan['accesses'][1]['address'] = rows[3]['address'] = '0xc00000f'
    observation = m.observe(plan, rows)
    assert not observation['complete']
    assert m.check(plan, observation)['status'] == 'inconclusive'
