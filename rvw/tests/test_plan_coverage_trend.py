"""Coverage trends compare measurement contexts, not sample counts."""
import json
from hashlib import sha256
import pytest
from rvw.plan import VPlan

pytestmark = pytest.mark.fast


def test_functional_trend_allows_more_traces_in_same_context(tmp_path):
    plan = tmp_path / 'plan.json'
    coverage = tmp_path / 'coverage.json'
    plan.write_text(json.dumps({'schema': 'rvw.vplan/1', 'requirements': {'R': 'Add'},
        'features': [{'id': 'add', 'requirements': ['R'],
                      'coverage': [{'path': 'coverage.json', 'groups': ['g']}]}]}))
    header = {'schema': 'rvw.rvfi/1', 'xlen': 32, 'isa': 'rv32i', 'core': 'fixture'}
    data = {'schema': 'rvw.functional-coverage/1', 'config_sha256': 'a'*64,
            'qualification_policy': 'c1-pass-complete-c2-v1',
            'traces': {'a': {'header': dict(header, elf='one', elf_sha256='1'*64, seed=1)}},
            'groups': {'g': {'expected_bins': 2, 'expected_hit': 1, 'holes': [[1]]}}}
    coverage.write_text(json.dumps(data))
    previous = tmp_path / 'before.json'
    before = VPlan(plan).status()
    context = sha256(json.dumps([header], sort_keys=True).encode()).hexdigest()
    assert before['features'][0]['coverage_contexts'] == ['functional:'+'a'*64+':'+context]
    previous.write_text(json.dumps(before))
    data['traces']['b'] = {'header': dict(header, elf='two', elf_sha256='2'*64, seed=2)}
    data['groups']['g'].update(expected_hit=2, holes=[])
    coverage.write_text(json.dumps(data))
    trend = VPlan(plan).status(previous)['features'][0]['trend']
    assert trend == {'status': 'comparable', 'hole_delta': -1, 'coverage_hit_delta': 1}
    data['traces']['b']['header']['xlen'] = 64
    coverage.write_text(json.dumps(data))
    assert VPlan(plan).status(previous)['features'][0]['trend']['status'] == 'incompatible_coverage_context'
