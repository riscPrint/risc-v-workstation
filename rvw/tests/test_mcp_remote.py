import pytest
pytest.importorskip('mcp')
from starlette.testclient import TestClient
from rvw.mcp.remote import Remote, ClientRegistry
from rvw.mcp.spec import ToolSpec, schema, ToolError


def make_registry(policy):
    return ClientRegistry([ToolSpec('fixture', 'fixture', schema({}), lambda: {'fixture': True})], project=policy.get('project'))


def test_remote_auth_and_owner_job_stores():
    app = Remote({'one': dict(tools=['fixture']), 'two': dict(tools=['fixture'])}, make_registry)
    with TestClient(app) as client:
        assert client.get('/messages').status_code == 401
        assert client.get('/missing', headers={'Authorization': 'Bearer one'}).status_code == 404
        a = app.clients['one'][0]
        b = app.clients['two'][0]
        job = a.jobs.submit('fixture', {}, lambda job: {})
        job.done.wait(2)
        with pytest.raises(ToolError):
            b.call('job_status', {'job_id': job.id})
        assert b.call('job_list', {}) == {'jobs': []}


def test_read_only_allowlist_and_project_binding():
    with pytest.raises(ValueError, match='read-only'):
        Remote({'token': dict(tools=['regress_run'], read_only=True)}, make_registry)
    registry = make_registry(dict(project='/project'))
    try:
        with pytest.raises(ToolError, match='project'):
            registry.call('fixture', {'project': '/other'})
    finally:
        registry.jobs.shutdown()


def test_authenticated_sse_protocol_roundtrip():
    import socket
    import threading
    import time
    import anyio
    import uvicorn
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    app = Remote({'token': dict(tools=['fixture'])}, make_registry)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]))
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started
        async def check():
            async with sse_client(f'http://127.0.0.1:{port}/sse', headers={'Authorization': 'Bearer token'}) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert 'fixture' in {t.name for t in tools.tools}
                    result = await session.call_tool('fixture', {})
                    assert not (result.is_error if hasattr(result, 'is_error') else result.isError)
                    import json
                    assert json.loads(result.content[0].text) == {'fixture': True}
        anyio.run(check)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        assert not thread.is_alive()


def test_client_budgets_are_not_global(monkeypatch):
    from rvw.mcp.jobs import JobManager
    a = JobManager(budget={'wall_seconds': 1})
    b = JobManager(budget={'wall_seconds': 2})
    try:
        first = a.submit('a', {}, lambda job: job.budget)
        second = b.submit('b', {}, lambda job: job.budget)
        assert first.done.wait(2) and second.done.wait(2)
        assert first.result != second.result
    finally:
        a.shutdown()
        b.shutdown()


def test_default_remote_registry_uses_budgeted_workers(tmp_path):
    app = Remote({'token': dict(tools=['evidence_query'], read_only=True, budget={'wall_seconds': 2})})
    registry = app.clients['token'][0]
    try:
        assert registry.tools['evidence_query'].long
        result = registry.call('evidence_query', dict(db=str(tmp_path / 'missing.sqlite')))
        job = registry.jobs.get(result['job_id'])
        assert job.done.wait(10)
        assert job.status == 'failed'
        assert job.cost_report is not None
    finally:
        registry.jobs.shutdown()
