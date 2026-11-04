"""Structural cones must not become proof-core or activation claims."""
import json

import pytest

from rvw.cov.proof_cones import report, validate_ids
from rvw.cov.proof import prove
from .test_proof import _setup, TINY, needs_sby


def cell(kind, ins, outs):
    return {'type': kind, 'connections': {'A': ins, 'Y': outs},
            'port_directions': {'A': 'input', 'Y': 'output'}}


def test_known_cone_and_separate_evidence():
    body = {'ports': {'inputs': {'direction': 'input', 'bits': [1, 4]}}, 'netnames': {'q': {'bits': [3]}}, 'cells': {
        'first': cell('$not', [1], [2]), 'second': cell('$dff', [2], [3]),
        'unused': cell('$not', [4], [5]), 'env': cell('$assume', [4], [])}}
    mapping = {'point_id': 'p', 'property_id': 'range', 'requirement_ids': ['req-range'], 'expression': 'q'}
    r = report({'bound_modules': {'h': body}}, 'h', [mapping],
               [{'unreachable': True, 'jobs': {'prove': {'status': 'PASS', 'exit_code': 0, 'free_wires': []}}}], {'sha256': 'abc'})
    names = {c['id']: c['name'] for c in r['logic']}
    p = r['properties'][0]
    assert {names[x] for x in p['cone']['cells']} == {'first', 'second'}
    assert [names[x] for x in r['outside_proven_cones']] == ['unused']
    assert p['proof_core']['cells'] is None
    assert p['activation']['status'] == 'not_measured'
    assert p['property_id'] == 'range' and p['requirement_ids'] == ['req-range']
    assert r['untested_assumptions'][0]['name'] == 'env'
    # A failed or unresolved property contributes no proven cone.
    for row, expr in [({'jobs': {}}, 'q'), ({'jobs': {'prove': {'status': 'PASS', 'exit_code': 0, 'free_wires': []}}}, 'missing'),
                      ({'jobs': {'prove': {'status': 'PASS', 'exit_code': 0}}}, 'q')]:
        r = report({'bound_modules': {'h': body}}, 'h', [{**mapping, 'expression': expr}], [row], {'sha256': 'abc'})
        assert len(r['outside_proven_cones']) == 3


def test_ids_are_validated():
    with pytest.raises(ValueError, match='unique'):
        validate_ids([{'point_id': 'a', 'property_id': 'same'}, {'point_id': 'b', 'property_id': 'same'}])
    with pytest.raises(ValueError, match='requirement_ids'):
        validate_ids([{'point_id': 'a', 'requirement_ids': 'not-a-list'}])


@needs_sby
def test_native_counter_proof_cone(tmp_path):
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})
    plan = json.loads(cfg.read_text())
    plan['points'][0].update(property_id='counter.range', requirement_ids=['counter.modulo3'])
    cfg.write_text(json.dumps(plan))
    r = prove(cfg, db, tmp_path / 'w', timeout=30)
    saved = json.loads((tmp_path / 'w/proof-cones.json').read_text())
    assert saved == r['proof_cones']
    p = saved['properties'][0]
    assert r['points'][0]['unreachable']
    assert p['proof_status'] == 'proven_conditional'
    assert p['cone']['status'] == 'structural_overapproximation'
    names = {c['id']: c['type'] for c in saved['logic']}
    assert '$add' in [names[x] for x in p['cone']['cells']]
    assert any('dff' in names[x] for x in p['cone']['cells'])
    assert not p['cone']['problems']


def test_refused_proof_does_not_contribute_a_proven_cone():
    body = {'ports': {'a': {'direction': 'input', 'bits': [1]}},
            'netnames': {'q': {'bits': [2]}}, 'cells': {'logic': cell('$not', [1], [2])}}
    mapping = {'point_id': 'p', 'expression': 'q'}
    row = {'unreachable': False, 'refused': 'sanity cover failed',
           'jobs': {'prove': {'status': 'PASS', 'exit_code': 0, 'free_wires': []}}}
    r = report({'bound_modules': {'h': body}}, 'h', [mapping], [row], {'sha256': 'abc'})
    assert r['properties'][0]['proof_status'] == 'not_proven'
    assert len(r['outside_proven_cones']) == 1


@pytest.mark.parametrize('job,guard,expected', [
    ({'status': 'PASS', 'exit_code': 0, 'free_wires': []}, True, 'reached'),
    ({'status': 'PASS', 'exit_code': 0, 'free_wires': []}, False, 'inconclusive'),
    ({'status': 'PASS', 'exit_code': 0}, True, 'inconclusive'),
    ({'status': 'PASS', 'exit_code': 1, 'free_wires': []}, True, 'inconclusive'),
    ({'status': 'FAIL', 'exit_code': 0, 'free_wires': []}, True, 'inconclusive'),
    ({'status': 'PASS', 'exit_code': 0, 'free_wires': ['undriven']}, True, 'inconclusive'),
])
def test_activation_needs_its_own_guarded_evidence(job, guard, expected):
    from rvw.cov.proof_cones import activation
    assert activation({'jobs': {'activation': job}, 'activation_guard': guard})['status'] == expected
    assert activation({'jobs': {'cover': job}})['status'] == 'not_measured'


@needs_sby
def test_native_activation_and_requirement_join(tmp_path):
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})
    plan = json.loads(cfg.read_text())
    plan['points'][0].update(property_id='counter.range', requirement_ids=['counter.modulo3'],
                             activation="s == 2'd1")
    cfg.write_text(json.dumps(plan))
    result = prove(cfg, db, tmp_path / 'work', timeout=30)['proof_cones']
    prop = result['properties'][0]
    assert prop['activation']['status'] == 'reached'
    assert prop['proof_core']['status'] == 'unavailable'
    requirement = result['requirements'][0]
    assert requirement['requirement_id'] == 'counter.modulo3'
    assert requirement['property_ids'] == ['counter.range']
    assert requirement['status'] == 'inconclusive'
