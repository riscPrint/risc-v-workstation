"""Slow HTTP/worker process tests without native cores."""
import json
import subprocess
import sys
import time

from test_remote_processes import ROOT, http, process_server
from rvw.farm.service import Queue
from rvw.farm.costs import configure, report


def worker(root):
    return subprocess.Popen([sys.executable, '-m', 'rvw', 'farm', 'queue',
                             '--root', str(root), '--operation', 'work'],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_running(queue, job_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = next(j for j in queue.jobs() if j['id'] == job_id)
        if job['state'] == 'running' and job.get('pgid'):
            return job
        time.sleep(.1)
    raise AssertionError('worker did not start')


def test_farm_http_workers_recovery_and_events(tmp_path, request):
    root = tmp_path / 'queue'
    queue = Queue(root)
    workers = []
    def start_worker():
        proc = worker(root)
        workers.append(proc)
        return proc
    def cleanup():
        for proc in workers:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        queue.recover(stale_after=0)
    request.addfinalizer(cleanup)
    configure(queue, 'agent:alice', {'jobs': 3})
    configure(queue, 'agent:bob', {'jobs': 1})
    tokens = tmp_path / 'tokens.json'
    tokens.write_text(json.dumps({'a': 'alice', 'b': 'bob'}))
    args = ['farm', 'serve', '--root', str(root), '--tokens', str(tokens)]
    command = [sys.executable, '-c', "import pathlib,time; p=pathlib.Path('{attempt_dir}/release')\nwhile not p.exists(): time.sleep(.05)"]
    with process_server(tmp_path, args) as (url, _):
        from urllib.error import HTTPError
        for headers in ({}, {'Authorization': 'Bearer wrong'}):
            try:
                http(url + '/runs', headers=headers)
            except HTTPError as exc:
                assert exc.code == 401
            else:
                raise AssertionError('unauthenticated farm access')
        low = http(url + '/runs', 'a', dict(command=command, priority=1, timeout=30, retries=1))
        high = http(url + '/runs', 'b', dict(command=command, priority=10, timeout=30))
        assert [j['id'] for j in http(url + '/runs', 'a')] == [low['id']]
        assert len(http(url + '/snapshot', 'a')['runs']) == 1
        w = start_worker()
        try:
            wait_running(queue, high['id'])
            (root / high['id'] / 'attempt-1' / 'release').touch()
            assert w.wait(timeout=15) == 0
        finally:
            if w.poll() is None:
                w.kill(); w.wait()
                queue.recover(stale_after=0)
        # Kill a queue controller with an active child, then explicitly recover.
        w = start_worker()
        try:
            wait_running(queue, low['id'])
            w.kill(); w.wait()
        finally:
            if w.poll() is None:
                w.kill(); w.wait()
                queue.recover(stale_after=0)
        recovered = queue.recover(stale_after=0)
        assert recovered[0]['state'] == 'queued'
        w = start_worker()
        wait_running(queue, low['id'])
        (root / low['id'] / 'attempt-2' / 'release').touch()
        assert w.wait(timeout=15) == 0
        assert next(j for j in queue.jobs() if j['id'] == low['id'])['state'] == 'complete'
        blocked = http(url + '/runs', 'b', dict(command=command, timeout=30))
        w = start_worker()
        assert w.wait(timeout=15) == 0
        assert next(j for j in queue.jobs() if j['id'] == blocked['id'])['state'] == 'budget_exhausted'
        sibling = http(url + '/workflows', 'a', dict(action='create', plan={'nodes': [dict(id='other', command=command)]}))
        plan = http(url + '/workflows', 'a', dict(action='create', plan={'nodes': [dict(id='one', command=command, timeout=30)]}))
        denied = False
        from urllib.error import HTTPError
        try:
            http(url + '/workflows', 'b', dict(action='status', workflow_id=plan['id']))
        except HTTPError as exc:
            denied = exc.code == 400
        assert denied
        state = http(url + '/workflows', 'a', dict(action='advance', workflow_id=plan['id']))
        node_job = state['nodes'][0]['job_id']
        w = start_worker()
        wait_running(queue, node_job)
        initial = http(url + '/events?workflow_id=' + plan['id'], 'a')
        assert 'running' in initial and 'complete' not in initial
        cursor = [int(line[4:]) for line in initial.splitlines() if line.startswith('id: ')][-1]
        # Restart HTTP service while the independent worker remains active.
    with process_server(tmp_path, args) as (url, _):
        assert w.poll() is None  # Worker remained active across service restart.
        (root / node_job / 'attempt-1' / 'release').touch()
        assert w.wait(timeout=15) == 0
        state = http(url + '/workflows', 'a', dict(action='status', workflow_id=plan['id']))
        assert state['state'] == 'complete'
        resumed = http(url + '/events?workflow_id=' + plan['id'], 'a',
                       headers={'Last-Event-ID': str(cursor)})
        resumed_ids = [int(line[4:]) for line in resumed.splitlines() if line.startswith('id: ')]
        assert resumed_ids and min(resumed_ids) > cursor and 'complete' in resumed
        events = initial + resumed
        try:
            http(url + '/events?workflow_id=' + plan['id'], 'b')
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError('foreign plan subscription accepted')
        assert sibling['id'] not in events and low['id'] not in events
        rows = [json.loads(line[6:]) for line in events.splitlines() if line.startswith('data: ')]
        assert [e['state'] for e in rows if 'job_id' not in e] == ['planned', 'pending', 'complete']
        assert any(e.get('node') == 'one' and e['state'] == 'running' for e in rows)
        ids = [int(line[4:]) for line in events.splitlines() if line.startswith('id: ')]
        assert ids == sorted(set(ids))
        assert 'running' in events and 'complete' in events
        assert plan['id'] not in http(url + '/events', 'b')
        assert 'id: ' not in http(url + '/events?workflow_id=' + plan['id'], 'a', headers={'Last-Event-ID': str(ids[-1])})
        assert report(queue, 'agent:alice')['usage']['jobs'] == 3
        assert report(queue, 'agent:bob')['usage']['jobs'] == 1
