import json
from argparse import Namespace
import pytest
from rvw.formal.testplan import build, html, run


def plan():
    return {'schema': 'rvw.formal-testplan/1', 'properties': [
        {'property_id': 'p', 'module': 'Top', 'origin': 'generated',
         'requirement_ids': ['R1'], 'mutation_ids': [1, 2],
         'source': {'file': 'Top.scala', 'line': 12}},
        {'property_id': 'q', 'module': 'Child', 'origin': 'hand_written'}]}


def test_evidence_joins_and_missing_obligations():
    data = build(plan(), [
        {'kind': 'result', 'property_id': 'p', 'data': {'schema': 'rvw.formal/1', 'status': 'pass', 'depth': 8, 'proof_kind': 'bounded'}},
        {'kind': 'core', 'data': {'schema': 'rvw.solver-core/1', 'property_id': 'p', 'status': 'pass', 'labels': ['init']}},
        {'kind': 'cones', 'data': {'schema': 'rvw.proof-cones/1', 'properties': [{'property_id': 'p', 'activation': {'status': 'reached'}}]}},
        {'kind': 'mutation', 'data': {'schema': 'rvw.mutation/2', 'mutants': [{'id': 1, 'state': 'killed'}]}}])
    p, q = data['properties']
    assert p['depth'] == 8 and p['mutation'][1]['state'] == 'missing'
    assert q['status'] == 'not_run' and q['proof_core']['status'] == 'unavailable'
    assert p['exclusion'] == 'not_authorized' and p['proof_core']['cell_coverage'] == 'unavailable'
    assert data['requirements'][0]['status'] == 'inconclusive'
    assert data['source_lines'][0]['activation_reached'] == 1
    assert len(data['modules']) == 2


def test_unknown_and_duplicate_ids_fail():
    with pytest.raises(ValueError, match='outside'):
        build(plan(), [{'kind': 'core', 'data': {'schema': 'rvw.solver-core/1', 'property_id': 'other'}}])
    p = plan()
    p['properties'].append(p['properties'][0])
    with pytest.raises(ValueError, match='unique'):
        build(p, [])


def test_html_escapes_source_text():
    p = plan()
    p['properties'][0]['module'] = '<script>alert(1)</script>'
    page = html(build(p, []))
    assert '<script>' not in page and '&lt;script&gt;' in page


def test_cli_capture_and_outputs(tmp_path):
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(plan()))
    out = tmp_path / 'out'
    assert run(Namespace(manifest=str(path), out=str(out), json=False)) == 1
    assert (out / 'report.html').exists()
    assert json.loads((out / 'result.json').read_text())['input_capture']


def test_generated_app_spec_is_an_inventory(tmp_path):
    spec = {'schema': 'rvw.formal-apps/1', 'top': 'Top', 'properties': [
        {'id': 'generated_check', 'module': 'Top', 'origin': 'generated', 'source': {'file': 'Top.scala', 'line': 9}}]}
    path = tmp_path / 'spec.json'
    path.write_text(json.dumps(spec))
    proof = tmp_path / 'generated_check'
    proof.mkdir()
    (proof / 'result.json').write_text(json.dumps({'schema': 'rvw.formal/1', 'status': 'pass', 'depth': 5, 'proof_kind': 'bounded'}))
    out = tmp_path / 'testplan'
    run(Namespace(manifest=str(path), out=str(out), json=False))
    report = json.loads((out / 'result.json').read_text())
    assert report['properties'][0]['status'] == 'pass'
    assert report['source_lines'][0]['line'] == 9


def test_explicit_core_alias_retains_native_id_and_activation():
    data = build(plan(), [{'kind': 'core', 'property_id': 'p', 'data': {
        'schema': 'rvw.solver-core/1', 'property_id': 'top:captured', 'status': 'pass', 'labels': ['guard'],
        'property_activation': [{'property_id': 'top:captured', 'status': 'not_reached_bounded'}]}}])
    row = data['properties'][0]
    assert row['proof_core']['captured_property_id'] == 'top:captured'
    assert row['activation']['status'] == 'not_reached_bounded'
    page = html(data)
    assert 'cell coverage' in page and 'unavailable' in page and 'guard' in page
