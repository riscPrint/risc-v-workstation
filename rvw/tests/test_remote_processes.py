"""Real CLI processes and official MCP SSE client. No core or native tools.

Run: nice -n 15 rvw/.venv/bin/python -m pytest rvw/tests/test_remote_processes.py -q
"""
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def process_server(tmp_path, args, env=None):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = (tmp_path / f'server-{port}.log').open('w+')
    proc = subprocess.Popen([sys.executable, '-m', 'rvw', *args,
                             '--host', '127.0.0.1', '--port', str(port)],
                            cwd=ROOT, env=env, stdout=log, stderr=log)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                log.seek(0)
                pytest.fail(log.read())
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    break
            except OSError:
                time.sleep(.1)
        else:
            pytest.fail('server startup timeout')
        yield f'http://127.0.0.1:{port}', proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()


def http(url, token=None, data=None, headers=None):
    req = Request(url, data=json.dumps(data).encode() if data is not None else None,
                  headers={**({'Authorization': 'Bearer ' + token} if token else {}),
                           **(headers or {})})
    with urlopen(req, timeout=15) as response:
        body = response.read().decode()
        return json.loads(body) if response.headers['Content-Type'] == 'application/json' else body


def test_mcp_process_isolation_and_lifecycle(tmp_path):
    pytest.importorskip('mcp')
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    # Importable fixture tools use the same worker path as real providers.
    (tmp_path / 'socket_fixture.py').write_text('''
import sys
from rvw.mcp.spec import ToolSpec, schema

def pause(job, seconds=0):
    rc = job.run([sys.executable, '-c', 'import time; time.sleep(' + str(seconds) + ')'])
    return {'returncode': rc}

def mcp_tools():
    return [ToolSpec('fixture_pause', 'bounded process', schema({'seconds': {'type': 'number'}}), pause, long=True)]
''')
    env = dict(os.environ, RVW_MCP_PLUGINS='socket_fixture',
               PYTHONPATH=str(tmp_path) + os.pathsep + os.environ.get('PYTHONPATH', ''))
    policy = tmp_path / 'clients.json'
    policy.write_text(json.dumps({'alice': {'tools': ['fixture_pause'], 'budget': {'wall_seconds': .5}},
                                  'bob': {'tools': ['fixture_pause'], 'budget': {'wall_seconds': 10}}}))
    args = ['mcp', '--transport', 'sse', '--clients', str(policy), '--profile', 'core']
    # Fixture has no profile; load all from this token's allowlist after initialization.
    async def connect(url, token, action):
        async with sse_client(url + '/sse', headers={'Authorization': 'Bearer ' + token}) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                return await action(client)

    async def call(client, name, args):
        result = await client.call_tool(name, args)
        return json.loads(result.content[0].text)

    ids = {}
    async def exercise(url):
        async def start(client):
            tools = await client.list_tools()
            assert 'job_status' in {t.name for t in tools.tools}
            await call(client, 'rvw_tools_load', {'profile': 'all'})
            return await call(client, 'fixture_pause', {'seconds': 2})
        a, b = await asyncio.gather(connect(url, 'alice', start), connect(url, 'bob', start))
        ids.update(alice=a['job_id'], bob=b['job_id'])
        assert ids['alice'] != ids['bob']
        async def check(client):
            foreign = await call(client, 'job_result', {'job_id': ids['alice']})
            assert foreign['status'] == 'error'
            own = await call(client, 'job_status', {'job_id': ids['bob'], 'wait_s': 10})
            assert own['status'] == 'done'  # disconnect did not cancel it
            cancelled = await call(client, 'fixture_pause', {'seconds': 10})
            state = await call(client, 'job_cancel', {'job_id': cancelled['job_id']})
            assert state['status'] in ('cancelled', 'cancelling')
            return own
        await connect(url, 'bob', check)
        async def exhausted(client):
            state = await call(client, 'job_status', {'job_id': ids['alice'], 'wait_s': 10})
            assert state['cost']['reason'] == 'budget_limit'
        await connect(url, 'alice', exhausted)
        # Leave a job in flight for graceful service restart.
        async def pending(client):
            job = await call(client, 'fixture_pause', {'seconds': 10})
            ids['pending'] = job['job_id']
        await connect(url, 'bob', pending)

    with process_server(tmp_path, args, env) as (url, _):
        for token in (None, 'wrong'):
            with pytest.raises(HTTPError) as exc:
                http(url + '/sse', token)
            assert exc.value.code == 401
        asyncio.run(exercise(url))
    with process_server(tmp_path, args, env) as (url, _):
        async def lost(client):
            state = await call(client, 'job_result', {'job_id': ids['pending']})
            assert state['status'] == 'error'
            assert 'restart' in state['error']
        asyncio.run(connect(url, 'bob', lost))
