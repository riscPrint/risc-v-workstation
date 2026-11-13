import sys
import pytest
from rvw.farm.service import Queue
from rvw.farm.workflows import workflow


def test_resume_dependency_and_completion(tmp_path):
    command = [sys.executable, '-c', 'pass']
    record = workflow(tmp_path, 'create', dict(nodes=[dict(id='a', command=command), dict(id='b', needs=['a'], command=command)]))
    wid = record['id']
    state = workflow(tmp_path, 'advance', workflow_id=wid)
    assert [n['state'] for n in state['nodes']] == ['queued', 'blocked']
    workflow(tmp_path, 'advance', workflow_id=wid)
    assert len(Queue(tmp_path).jobs()) == 1
    Queue(tmp_path).work_once()
    workflow(tmp_path, 'advance', workflow_id=wid)
    Queue(tmp_path).work_once()
    assert workflow(tmp_path, workflow_id=wid)['state'] == 'complete'
    events = Queue(tmp_path).events()
    assert events[-1]['workflow_id'] == wid
    assert Queue(tmp_path).events(events[-1]['seq']) == []


def test_invalid_dag_and_owner(tmp_path):
    with pytest.raises(ValueError, match='cyclic'):
        workflow(tmp_path, 'create', dict(nodes=[dict(id='a', needs=['a'], command=['true'])]))
    record = workflow(tmp_path, 'create', dict(nodes=[dict(id='a', command=['true'])]))
    with pytest.raises(ValueError, match='owner'):
        workflow(tmp_path, workflow_id=record['id'], owner='other')


def test_event_stream_owner_filter_and_cursor(tmp_path):
    import json
    import threading
    from urllib.request import Request, urlopen
    from rvw.farm.http import server
    q = Queue(tmp_path)
    q.submit('alice', ['true'])
    bob = q.submit('bob', ['true'])
    http = server(tmp_path, {'secret': 'alice'}, port=0)
    thread = threading.Thread(target=http.serve_forever)
    thread.start()
    try:
        url = 'http://127.0.0.1:' + str(http.server_port) + '/events'
        req = Request(url, headers={'Authorization': 'Bearer secret'})
        data = urlopen(req).read().decode()
        assert 'data:' in data
        assert bob['id'] not in data
        last = max(e['seq'] for e in q.events())
        req = Request(url, headers={'Authorization': 'Bearer secret', 'Last-Event-ID': str(last)})
        assert 'data:' not in urlopen(req).read().decode()
    finally:
        http.shutdown()
        thread.join()
        http.server_close()


@pytest.mark.parametrize('verdict,state', [('reject', 'dut_failure'), ('inconclusive', 'inconclusive'), ('accept', 'complete')])
def test_collected_gate_verdict_decides_dependency(tmp_path, verdict, state):
    gate = [sys.executable, '-c', "import json;from pathlib import Path;Path('verdict.json').write_text("
            f"json.dumps(dict(schema='rvw.verdict/2',verdict='{verdict}',tests='pass')))"]
    record = workflow(tmp_path, 'create', dict(nodes=[dict(id='gate', command=gate),
                                                      dict(id='merge', needs=['gate'], command=[sys.executable, '-c', 'pass'])]))
    workflow(tmp_path, 'advance', workflow_id=record['id'])
    Queue(tmp_path).work_once()
    nodes = workflow(tmp_path, 'advance', workflow_id=record['id'])['nodes']
    assert nodes[0]['state'] == state
    assert (nodes[1]['state'] == 'queued') == (verdict == 'accept')
