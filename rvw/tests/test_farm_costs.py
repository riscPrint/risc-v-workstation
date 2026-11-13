import sys
from rvw.farm.service import Queue
from rvw.farm.costs import configure, report


def test_shared_project_job_budget(tmp_path):
    q = Queue(tmp_path)
    configure(q, 'project:p', dict(jobs=1), 2.)
    q.submit('a', [sys.executable, '-c', 'pass'], project='p')
    q.submit('b', [sys.executable, '-c', 'pass'], project='p')
    assert q.work_once()['state'] == 'complete'
    assert q.work_once() is None
    assert q.jobs()[1]['state'] == 'budget_exhausted'
    costs = report(q, 'project:p')
    assert costs['usage']['jobs'] == 1
    assert costs['cost'] >= 0


def test_wall_budget_enforced(tmp_path):
    q = Queue(tmp_path)
    job = q.submit('agent', [sys.executable, '-c', 'import time; time.sleep(10)'])
    configure(q, 'run:' + job['id'], dict(wall_seconds=.1))
    assert q.work_once()['state'] == 'budget_exhausted'
    assert report(q, 'run:' + job['id'])['usage']['wall_seconds'] >= .1


def test_active_reservation_prevents_parallel_overspend(tmp_path):
    q = Queue(tmp_path)
    configure(q, 'agent:a', dict(core_hours=1 / 3600))
    q.submit('a', ['true'], timeout=1)
    q.submit('a', ['true'], timeout=1)
    assert q.claim()['state'] == 'running'
    assert q.claim() is None
    assert q.jobs()[1]['state'] == 'queued'
