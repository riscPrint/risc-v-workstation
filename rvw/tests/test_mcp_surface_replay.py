"""Slow stdio replay for the reviewed call rows. This is fixture coverage."""
import json
import os
import sys
from pathlib import Path

import anyio
import pytest
from jsonschema import validate

FIXTURE = Path(__file__).parent / 'fixtures' / 'mcp-surface'


def test_stdio_surface_replay(tmp_path, gcd_db):
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    checkout = Path(__file__).resolve().parents[2]
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'rvw.toml').write_text('''[project]
schema = "rvw.project/1"
root = "."
[core]
name = "surface-fixture"
backend = "riscvsim-verilator"
adapter = ["python3", "adapter.py"]
configs = ["tiny"]
default_config = "tiny"
''')
    out = tmp_path / 'out'
    out.mkdir()
    rows = json.loads((FIXTURE / 'calls.json').read_text())
    values = dict(fixture=str(FIXTURE.resolve()), checkout=str(checkout), db=str(gcd_db), out=str(out))
    def expand(value):
        if isinstance(value, str):
            return value.format(**values)
        if isinstance(value, list):
            return [expand(x) for x in value]
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        return value
    env = {**os.environ, 'RVW_PROJECT': str(project), 'RVW_HOME': str(checkout),
           'RVW_DESIGNDB': str(gcd_db), 'RVW_MCP_SYNC_S': '1'}
    env.pop('RVW_MCP_PLUGINS', None)
    params = StdioServerParameters(command=sys.executable, args=['-m', 'rvw', 'mcp', '--profile', 'all'], env=env)
    failures = []
    called = []

    async def replay():
        with (tmp_path / 'server.log').open('w') as log:
            async with stdio_client(params, errlog=log) as streams:
                async with ClientSession(*streams[:2]) as session:
                    await session.initialize()
                    tools = {t.name: t for t in (await session.list_tools()).tools}
                    assert not set(rows) - tools.keys(), 'Removed tools need a reviewed argument-table update.'
                    async def call(name, args):
                        with anyio.fail_after(75):
                            result = await session.call_tool(name, args)
                        return json.loads(next(c.text for c in result.content if c.type == 'text'))
                    for name, row in rows.items():
                        arguments = expand(row['arguments'])
                        tool = tools[name]
                        validate(arguments, getattr(tool, 'input_schema', None) or tool.inputSchema)
                        result = await call(name, arguments)
                        if result.get('job_id'):
                            job_id = result['job_id']
                            state = await call('job_status', dict(job_id=job_id, wait_s=60))
                            if state['status'] not in ('done', 'failed', 'cancelled'):
                                await call('job_cancel', dict(job_id=job_id))
                                failures.append((name, 'job did not finish'))
                                continue
                            fetched = await call('job_result', dict(job_id=job_id))
                            assert fetched.get('result') == state.get('result'), name
                            result = state.get('result', state)
                        if not isinstance(result, dict):
                            result = {'result': result}
                        text = json.dumps(result)
                        if 'Traceback (most recent call last)' in text or result.get('code') in ('internal_error', 'invalid_arguments'):
                            failures.append((name, result))
                        if result.get('status') == 'ok' and result.get('verdict') == 'fail':
                            failures.append((name, 'failed verdict reported ok'))
                        if 'out' in arguments and not result.get('error') and result.get('status') not in ('error', 'failed', 'inconclusive', 'unsupported', 'not_installed'):
                            if not Path(arguments['out']).exists():
                                failures.append((name, 'declared output does not exist'))
                        called.append(name)
    anyio.run(replay)
    assert len(called) >= 60
    assert not failures, failures
