import json
import pytest
from rvw.farm.service import Queue
from rvw.farm.live import snapshot, bundle
from rvw.results import SuiteResults, TestEntry, save_results


def test_live_runs_trends_history_clusters_and_bundle(tmp_path):
    q = Queue(tmp_path)
    job = q.submit('alice', ['true'])
    foreign = q.submit('bob', ['true'])
    root = tmp_path / job['id']
    root.mkdir()
    save_results(SuiteResults('run', 'fixture', 'generic', 'small', '2026-11-13T00:00:00Z', tests=[
        TestEntry('test', 'assert', signature='assert:Unit.scala:12', run='cell')]), root)
    target = root / 'cell' / 'bundle'
    target.mkdir(parents=True)
    (target / 'summary.json').write_text('{"schema":"rvw.bundle/1","status":"assert"}')
    view = snapshot(q, 'alice')
    assert len(view['runs']) == 1
    assert view['trends'][0]['pass_rate'] == 0
    assert len(view['test_history']) == 1
    assert view['failure_clusters'][0]['bundles'] == ['cell/bundle/summary.json']
    assert bundle(q, 'alice', job['id'], 'cell/bundle/summary.json')['status'] == 'assert'
    with pytest.raises(ValueError, match='owner'):
        bundle(q, 'alice', foreign['id'], 'cell/bundle/summary.json')
    with pytest.raises(ValueError, match='within'):
        bundle(q, 'alice', job['id'], '../summary.json')


def test_missing_evidence_has_no_zero_sample(tmp_path):
    q = Queue(tmp_path)
    q.submit('alice', ['true'])
    view = snapshot(q, 'alice')
    assert view['runs'][0]['evidence'] == 'no_checks'
    assert view['trends'][0]['pass_rate'] is None
