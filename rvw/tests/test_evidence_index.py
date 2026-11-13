import hashlib
import json
from rvw.evidence.index import build, query


import pytest

pytestmark = pytest.mark.fast


def test_cross_tool_query_preserves_originals_and_dependencies(tmp_path):
    dependency = tmp_path / 'inputs.txt'
    dependency.write_text('captured')
    raw = dict(schema='rvw.formal/1', status='pass', config='small', assumptions=['reset is asserted'],
        evidence_dependencies=[dict(path='inputs.txt', sha256=hashlib.sha256(dependency.read_bytes()).hexdigest())])
    report = tmp_path / 'formal.json'
    report.write_text(json.dumps(raw))
    before = report.read_bytes()
    db = tmp_path / 'index.sqlite'
    assert build(tmp_path, db)['indexed'] == 1
    result = query(db, 'small')['matches'][0]
    assert result['integrity'] == 'unchanged'
    assert result['validation'] == 'json_only'
    assert result['assumptions'] == ['reset is asserted']
    dependency.unlink()
    assert query(db)['matches'][0]['integrity'] == 'inconclusive'
    assert report.read_bytes() == before


def test_changed_or_missing_original_weakens_record(tmp_path):
    report = tmp_path / 'lint.json'
    report.write_text('{"schema":"rvw.lint/1","status":"pass"}')
    db = tmp_path / 'index.sqlite'
    build(tmp_path, db)
    report.write_text('{"schema":"rvw.lint/1","status":"fail"}')
    record = query(db)['matches'][0]
    assert record['recorded_status'] == 'pass'
    assert record['integrity'] == 'inconclusive'
    report.unlink()
    assert 'report missing' in query(db)['matches'][0]['issues']


def test_invalid_c1_and_no_matches(tmp_path):
    (tmp_path / 'result.json').write_text('{"schema":"rvw.run/1","status":"imagined"}')
    db = tmp_path / 'index.sqlite'
    build(tmp_path, db)
    assert query(db)['matches'][0]['integrity'] == 'inconclusive'
    assert query(db, 'no such claim')['status'] == 'no_checks'


@pytest.mark.parametrize('schema', [
    'rvw.functional-coverage/1', 'rvw.rtl-coverage/1', 'rvw.probe-coverage/1',
    'rvw.source-coverage/1', 'rvw.fp-coverage/1',
])
def test_index_includes_all_measured_coverage_families(tmp_path, schema):
    report = tmp_path/'coverage.json'
    data = {'schema': schema, 'groups': {}, 'status': 'reported'}
    report.write_text(json.dumps(data))
    database = tmp_path/'index.sqlite'
    assert build(tmp_path, database)['indexed'] == 1
    matches = query(database, schema=schema)['matches']
    assert len(matches) == 1
    assert matches[0]['observations'] == data
    assert matches[0]['validation'] == 'json_only'
    assert matches[0]['integrity'] == 'unchanged'
