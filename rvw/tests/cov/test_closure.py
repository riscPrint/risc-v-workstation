import json
import pytest
from rvw.cov.cli import execute_json


def test_closure_ranks_declared_tests_without_claiming_hits(tmp_path):
    r = tmp_path / 'report.json'
    c = tmp_path / 'candidates.json'
    r.write_text(json.dumps({'schema': 'rvw.functional-coverage/1', 'groups': {
        'sem_add_rs1': {'holes': [['signed_min'], ['zero']]}}}))
    c.write_text(json.dumps({'schema': 'rvw.coverage-candidates/1', 'tests': [
        {'id': 'boundary', 'targets': ['sem_add*'], 'priority': 2, 'reason': 'Exercises integer boundaries'},
        {'id': 'add', 'targets': ['*'], 'priority': 1, 'reason': 'Exercises add'}]}))
    out = execute_json('closure', database=r, candidates=c)
    assert len(out['unhit']) == 2
    assert out['unhit'][0]['reachability'] == 'undetermined'
    assert [t['id'] for t in out['unhit'][0]['candidate_tests']] == ['boundary', 'add']
    assert not out['unhit'][0]['excluded']
    assert out['report_sha256']
    c.write_text(json.dumps({'schema': 'rvw.coverage-candidates/1', 'tests': [
        {'id': 'x', 'targets': [], 'priority': 1, 'reason': 'x'}]}))
    with pytest.raises(ValueError, match='invalid candidate'):
        execute_json('closure', database=r, candidates=c)


def test_excluded_is_not_a_new_unreachable_claim(tmp_path):
    r = tmp_path / 'report.json'
    c = tmp_path / 'candidates.json'
    r.write_text(json.dumps({'schema': 'rvw.coverage/1', 'tests': {}, 'points': [
        {'id': 'x', 'count': 0, 'exclusion': {'unreachable': True}}]}))
    c.write_text(json.dumps({'schema': 'rvw.coverage-candidates/1', 'tests': []}))
    out = execute_json('closure', database=r, candidates=c)
    assert out['unhit'][0]['excluded'] is True
    assert out['unhit'][0]['reachability'] == 'undetermined'
    assert out['unhit'][0]['candidate_tests'] == []


def test_closure_uses_the_proof_guard(tmp_path, monkeypatch):
    from rvw.cov import proof
    r, c, e = [tmp_path / n for n in ('r.json', 'c.json', 'e.json')]
    r.write_text(json.dumps({'schema': 'rvw.coverage/1', 'tests': {}, 'points': [{'id': 'x', 'count': 0}]}))
    c.write_text(json.dumps({'schema': 'rvw.coverage-candidates/1', 'tests': []}))
    e.write_text(json.dumps({'points': [{'point_id': 'x', 'unreachable': True}]}))
    calls = []
    def guard(data, path):
        calls.append(path)
        data['points'][0]['exclusion'] = {'unreachable': True}
        return data
    monkeypatch.setattr(proof, 'apply_exclusions', guard)
    out = execute_json('closure', database=r, candidates=c, exclusions=e)
    assert calls == [e]
    assert out['unhit'][0]['reachability'] == 'proven-unreachable'


def test_text_report_lists_holes_and_candidates(capsys):
    from types import SimpleNamespace
    from rvw.cov.cli import emit
    emit(SimpleNamespace(json=False, out=None), {'schema': 'rvw.coverage-closure/1', 'unhit': [
        {'id': 'bin', 'reachability': 'undetermined', 'excluded': False,
         'candidate_tests': [{'id': 'test'}]}]})
    text = capsys.readouterr().out
    assert '1 unhit bins' in text
    assert 'candidates=test' in text
    assert 'reachability=undetermined' in text


def test_closure_includes_uncompleted_rtl_sequences(tmp_path):
    r, c = tmp_path / 'rtl.json', tmp_path / 'candidates.json'
    r.write_text(json.dumps({'schema': 'rvw.rtl-coverage/1', 'status': 'ok', 'bins': [],
        'sequences': [{'id': 'request-response', 'completed': 0, 'pending': 1}]}))
    c.write_text(json.dumps({'schema': 'rvw.coverage-candidates/1', 'tests': []}))
    hole = execute_json('closure', database=r, candidates=c)['unhit'][0]
    assert hole['id'] == 'request-response'
    assert hole['pending'] == 1
    assert hole['reachability'] == 'undetermined'


def test_native_literal_catalog_does_not_scan_each_pattern(tmp_path,monkeypatch):
    import importlib
    module=importlib.import_module('rvw.cov.closure')
    points=[{'id':f'{i:064x}','count':0} for i in range(100)]
    r,c=tmp_path/'code.json',tmp_path/'candidates.json'
    r.write_text(json.dumps({'schema':'rvw.coverage/1','tests':{},'points':points}))
    c.write_text(json.dumps({'schema':'rvw.coverage-candidates/1','tests':[
        {'id':'candidate','targets':[p['id'] for p in points],'priority':1,'reason':'measured signatures'}]}))
    monkeypatch.setattr(module,'fnmatchcase',lambda *args:pytest.fail('literal native IDs need no wildcard scan'))
    result=module.closure(r,c)
    assert len(result['unhit'])==100
    assert all(h['candidate_tests'][0]['id']=='candidate' for h in result['unhit'])
