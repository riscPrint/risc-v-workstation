import sys
import threading
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from rvw.farm.service import Queue
from rvw.farm.http import server


def test_queue_restart_priority_fairness(tmp_path):
    q = Queue(tmp_path)
    a = q.submit('a', [sys.executable, '-c', 'pass'])
    b = q.submit('b', [sys.executable, '-c', 'pass'], priority=2)
    assert Queue(tmp_path).work_once()['id'] == b['id']
    assert q.work_once()['id'] == a['id']
    assert q.work_once() is None
    assert len(q.events()) >= 4


def test_retry_preserves_attempts(tmp_path):
    q = Queue(tmp_path)
    q.submit('a', [sys.executable, '-c', 'import sys; sys.exit(1)'], retries=1)
    assert q.work_once()['state'] == 'queued'
    result = q.work_once()
    assert result['state'] == 'error'
    assert [a['status'] for a in result['attempts']] == ['error', 'error']


def test_cancel_queued_and_recovery(tmp_path):
    q = Queue(tmp_path)
    job = q.submit('a', ['missing-command'])
    with pytest.raises(StopIteration):
        q.cancel(job['id'], 'b')
    assert q.cancel(job['id'], 'a')['state'] == 'cancelled'
    q.submit('a', ['missing-command'])
    assert q.work_once()['state'] == 'infrastructure_error'


def test_http_auth_owner_isolation(tmp_path):
    http = server(tmp_path, {'secret': 'alice', 'other': 'bob'}, port=0)
    thread = threading.Thread(target=http.serve_forever)
    thread.start()
    base = 'http://127.0.0.1:' + str(http.server_port)
    try:
        with pytest.raises(HTTPError) as e:
            urlopen(base + '/runs')
        assert e.value.code == 401
        req = Request(base + '/runs', json.dumps({'command': ['true'], 'owner': 'bob'}).encode(), headers={'Authorization': 'Bearer secret'})
        assert json.load(urlopen(req))['owner'] == 'alice'
        req = Request(base + '/runs', headers={'Authorization': 'Bearer other'})
        assert json.load(urlopen(req)) == []
    finally:
        http.shutdown()
        thread.join()
        http.server_close()


def test_dead_worker_requeues_without_losing_attempt(tmp_path):
    q = Queue(tmp_path)
    q.submit('a', ['true'], retries=1)
    job = q.claim()
    q.update(job['id'], controller=2147483647, heartbeat=0)
    recovered = Queue(tmp_path).recover()
    assert recovered[0]['state'] == 'queued'
    assert recovered[0]['attempts'][0]['status'] == 'infrastructure_error'


def test_running_cancel_acknowledged_after_cleanup(tmp_path):
    import time
    q = Queue(tmp_path)
    job = q.submit('a', [sys.executable, '-c', 'import time; time.sleep(30)'])
    thread = threading.Thread(target=q.work_once)
    thread.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if q.jobs()[0].get('pgid'):
            break
        time.sleep(.02)
    assert q.cancel(job['id'], 'a')['state'] == 'cancel_requested'
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert q.jobs()[0]['state'] == 'cancelled'
    assert q.jobs()[0]['pgid'] is None


def test_declared_dut_retry_keeps_failure_and_classifies_flakiness(tmp_path):
    q = Queue(tmp_path)
    code = """import json
from pathlib import Path
p=Path.cwd()
status='fail' if p.name=='attempt-1' else 'pass'
r=dict(schema='rvw.run/1',status=status,core='generic',config='small',elf_sha256='a'*64,rtl_sha256='b'*64,seed=1,tools={'native_build':{'sha256':'c'*64}})
(p/'result.json').write_text(json.dumps(r))
"""
    q.submit('a', [sys.executable, '-c', code], retries=1, retry_on=['dut_failure'])
    assert q.work_once()['state'] == 'queued'
    result = q.work_once()
    assert result['state'] == 'dut_failure'
    assert result['observed_dut_failure'] and result['unstable']
    assert [a['dut_status'] for a in result['attempts']] == ['fail', 'pass']
