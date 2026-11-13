import copy
import json
import sys

import pytest
from rvw.farm.batch import collect, render
from rvw.farm.k8s_validate import validate
from rvw.farm.shard_plan import plan

pytestmark = pytest.mark.fast


def fixture(tmp_path):
    elf = tmp_path / 'add.elf'
    elf.write_bytes(b'ELF input')
    manifest = tmp_path / 'input.jsonl'
    manifest.write_text(json.dumps(dict(elf=str(elf), config='test', seed=7)) + '\n')
    root = tmp_path / 'shared'
    document = plan(manifest, ['/tools/run.sh'], root, 'needs-build', 'results',
                    persistent=True, python=sys.executable)
    cell = root / 'shards/0/cells/0'
    cell.mkdir(parents=True)
    expected = document['shards'][0]['results'][0]['identity']
    (cell / 'result.json').write_text(json.dumps(dict(schema='rvw.run/1', core='fixture', status='fail',
                                                   source={}, **expected)))
    suite = dict(schema='rvw.results/1', run_id='fixture', suite='isa', core='fixture', config='test',
                 created='2026-11-13T00:00:00Z', source={}, tests=[dict(status='fail', signature='fixture-failure',
                 **document['shards'][0]['results'][1]['tests'][0])])
    path = root / 'shards/0/results.json'
    path.write_text(json.dumps(suite))
    return document, root, path, suite


def test_persistent_plan_preserves_test_id_and_checks_both_contracts(tmp_path):
    document, root, _, _ = fixture(tmp_path)
    shard = document['shards'][0]
    assert shard['command'][:6] == ['nice', '-n', '10', sys.executable, '-m', 'rvw.farm.native_shard']
    assert json.loads((root / 'shard-0.jsonl').read_text())['id'] == 'add.elf'
    assert render(document)['items'][0]['spec']['template']['spec']['containers'][0]['command'] == shard['command']
    report = collect(document, root)
    assert report['status'] == 'complete'  # A real DUT failure is still complete collection.
    assert report['evidence'][0]['status'] == 'fail'
    assert report['evidence'][1]['tests'] == 1


@pytest.mark.parametrize('change', ['config', 'id', 'status', 'count', 'source'])
def test_c3_does_not_hide_changed_identity_or_outcome(tmp_path, change):
    document, root, path, suite = fixture(tmp_path)
    if change == 'config':
        suite['config'] = 'other'
    elif change == 'count':
        suite['tests'] = []
    elif change == 'source':
        suite['source'] = {'core_rev': 'different'}
    else:
        suite['tests'][0][change] = 'pass' if change == 'status' else 'wrong'
    path.write_text(json.dumps(suite))
    assert collect(document, root)['status'] == 'inconclusive'


def test_persistent_rejects_parallel_server_jobs(tmp_path):
    with pytest.raises(ValueError, match='jobs=1'):
        plan(tmp_path / 'missing', ['adapter'], tmp_path / 'out', 'image', 'claim', jobs=2, persistent=True)


def test_offline_schema_and_negative_control(tmp_path):
    document, _, _, _ = fixture(tmp_path)
    manifest = render(document)
    schema = tmp_path / 'openapi.json'
    # A small schema fixture. The native report uses the pinned official schema.
    schema.write_text(json.dumps({'definitions': {'io.k8s.api.batch.v1.Job': {'type': 'object',
        'required': ['spec'], 'properties': {'spec': {'type': 'object', 'properties': {'template': {
        'type': 'object', 'properties': {'spec': {'type': 'object', 'required': ['containers']}}}}}}}}}))
    assert validate(manifest, schema)['status'] == 'valid'
    missing = copy.deepcopy(manifest)
    del missing['items'][0]['spec']['template']['spec']['containers']
    assert validate(missing, schema)['status'] == 'invalid'
    manifest['items'][0]['apiVersion'] = 'batch/v2'
    assert validate(manifest, schema)['status'] == 'invalid'
