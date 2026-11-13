"""Opt-in native remote checks. Requires a private, prepared VexRiscv project.

Set RVW_REMOTE_NATIVE_PROJECT to its rvw.toml. Source the native environment.
Set RVW_VEX_LOCK=vex-remotemcp, RVW_SBT_LOCK=sbt-remotemcp and
RISCVSIM_MAKE_JOBS=2. Generated results stay beside the private project.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from test_remote_processes import ROOT, http, process_server
from test_farm_processes import worker
from rvw.farm.service import Queue
from rvw.farm.costs import configure, report

PROJECT = os.environ.get('RVW_REMOTE_NATIVE_PROJECT')
pytestmark = pytest.mark.skipif(not PROJECT, reason='set RVW_REMOTE_NATIVE_PROJECT to a private prepared VexRiscv project')


def test_native_mcp_project_job(tmp_path):
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    project = Path(PROJECT).resolve()
    out = project.parent / ('remote-' + str(time.time_ns()))
    policy = tmp_path / 'native-clients.json'
    policy.write_text(json.dumps({'native': {'tools': ['regress_list', 'regress_run'],
                                            'project': str(project), 'budget': {'wall_seconds': 110}}}))
    async def exercise(url):
        async with sse_client(url + '/sse', headers={'Authorization': 'Bearer native'}) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                async def call(name, args):
                    data = await client.call_tool(name, args)
                    data = json.loads(data.content[0].text)
                    assert data['status'] != 'error', data
                    return data
                async def finished(job):
                    deadline = time.monotonic() + 140
                    while time.monotonic() < deadline:
                        state = await call('job_status', {'job_id': job['job_id'], 'wait_s': 30})
                        if state['status'] in ('done', 'failed', 'cancelled'):
                            (project.parent / 'remote-status.json').write_text(json.dumps(state, indent=2))
                            assert state['status'] == 'done', state
                            return await call('job_result', {'job_id': job['job_id']})
                    raise AssertionError('native job deadline')
                listing = await finished(await call('regress_list', {}))
                assert listing['result']
                arguments = {'suite': 'smoke', 'filter': ['^smoke$'], 'jobs': 1,
                             'seeds': 1, 'out': str(out), 'no_index': True, 'timeout': 90}
                running = await call('regress_run', arguments)
                another = await call('regress_run', {**arguments, 'out': str(out) + '-cancel'})
                cancelled = await call('job_cancel', {'job_id': another['job_id']})
                assert cancelled['status'] in ('cancelled', 'cancelling')
                state = await finished(running)
                assert state['result'], state
                suites = list(out.rglob('results.json'))
                assert suites, state
                for suite in suites:
                    data = json.loads(suite.read_text())
                    assert data.get('tests'), data
                    assert all(t['status'] == 'pass' for t in data['tests']), data
    with process_server(tmp_path, ['mcp', '--transport', 'sse', '--clients', str(policy)]) as (url, _):
        asyncio.run(exercise(url))


def test_native_farm_two_users(tmp_path):
    project = Path(PROJECT).resolve()
    root = project.parent / ('farm-' + str(time.time_ns()))
    queue = Queue(root)
    configure(queue, 'agent:alice', {'jobs': 1, 'wall_seconds': 105})
    configure(queue, 'agent:bob', {'jobs': 1, 'wall_seconds': 110})
    tokens = tmp_path / 'native-tokens.json'
    tokens.write_text(json.dumps({'a': 'alice', 'b': 'bob'}))
    command = [sys.executable, '-m', 'rvw', '--project', str(project), 'regress', 'run',
               '--suite', 'isa', '--jobs', '1', '--out', '{attempt_dir}/suite', '--no-index', '--json']
    with process_server(tmp_path, ['farm', 'serve', '--root', str(root), '--tokens', str(tokens)]) as (url, _):
        a = http(url + '/runs', 'a', dict(command=command, priority=1, timeout=115))
        b = http(url + '/runs', 'b', dict(command=command, priority=10, timeout=115))
        failures = []
        # Serial native workers stay below the two-job host limit.
        for expected, token in ((b, 'b'), (a, 'a')):
            w = worker(root)
            try:
                deadline = time.monotonic() + 140
                while w.poll() is None:
                    assert time.monotonic() < deadline, 'native worker deadline'
                    http(url + '/snapshot', token)
                    time.sleep(2)
                assert w.returncode == 0
            finally:
                if w.poll() is None:
                    queue.cancel(expected['id'], expected['owner'])
                    try:
                        w.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        w.kill(); w.wait()
                        queue.recover(stale_after=0)
            owned = http(url + '/runs', token)
            (project.parent / ('farm-status-' + token + '.json')).write_text(json.dumps(owned, indent=2))
            assert owned[0]['id'] == expected['id']
            if owned[0]['state'] != 'complete':
                failures.append({'owner': owned[0]['owner'], 'state': owned[0]['state']})
                continue
            suites = list((root / expected['id']).rglob('results.json'))
            if not suites:
                failures.append({'owner': owned[0]['owner'], 'state': 'missing C3'})
                continue
            data = json.loads(suites[0].read_text())
            assert len(data['tests']) == 49 and all(t['status'] == 'pass' for t in data['tests']), data
        assert report(queue, 'agent:alice')['usage']['jobs'] == 1
        assert report(queue, 'agent:bob')['usage']['jobs'] == 1
        assert not failures, failures
