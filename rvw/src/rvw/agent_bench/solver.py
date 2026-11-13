"""A deterministic MCP evidence client. Expected source lines stay evaluator-only."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import anyio

WORKFLOW = ('regress_run', 'cosim_check', 'bundle_make', 'query_drivers', 'wave_why')


def locations(value):
    """Keep the tools' traversal order, with one candidate per source line."""
    found = []
    def visit(node):
        if isinstance(node, dict):
            loc = node.get('loc')
            if isinstance(loc, str) and loc.rsplit(':', 1)[-1].isdigit() and loc not in found:
                found.append(loc)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    return found


def rank(candidates, source, line):
    # Full relative source suffix, never just the basename.
    target = source.replace('\\', '/').lstrip('./')
    for index, location in enumerate(candidates, 1):
        file, number = location.rsplit(':', 1)
        if int(number) == line and (file == target or file.endswith('/' + target)):
            return index
    return None


async def solve(call, steps, *, max_calls=32, budget_s=110):
    if tuple(s['tool'] for s in steps) != WORKFLOW:
        raise ValueError('expected regression, cosim, bundle, drivers, wave why workflow')
    if max_calls < 1 or budget_s <= 0:
        raise ValueError('budgets must be positive')
    started = time.monotonic()
    transcript, used = [], 0

    async def bounded(tool, arguments):
        nonlocal used
        if used >= max_calls:
            raise RuntimeError('tool budget exhausted')
        used += 1
        return await call(tool, arguments)

    with anyio.move_on_after(budget_s) as scope:
        for step in steps:
            before = time.monotonic()
            record = {'tool': step['tool'], 'arguments': step['arguments']}
            transcript.append(record)
            try:
                result = await bounded(step['tool'], step['arguments'])
                while isinstance(result, dict) and result.get('job_id') and result.get('status') in ('queued', 'running'):
                    result = await bounded('job_status', {'job_id': result['job_id'], 'wait_s': 30})
                if isinstance(result, dict) and result.get('job_id') and result.get('status') in ('failed', 'cancelled'):
                    raise RuntimeError(json.dumps(result))
                if isinstance(result, dict) and result.get('status') == 'done' and 'job_id' in result:
                    result = result['result']
                record['result'] = result
            except Exception as exc:
                record['error'] = str(exc)
            finally:
                record['wall_s'] = time.monotonic() - before
    candidates = locations([r.get('result', {}) for r in transcript if r['tool'] in ('query_drivers', 'wave_why')])
    complete = len(transcript) == len(WORKFLOW) and all('result' in r and 'error' not in r for r in transcript)
    return {'schema': 'rvw.agent-evidence-solver/1', 'track': 'native-tools',
            'status': 'observed' if complete and not scope.cancel_called else 'inconclusive',
            'wall_s': time.monotonic() - started, 'calls': used, 'timed_out': scope.cancel_called,
            'transcript': transcript, 'candidates': candidates, 'repair': 'NOT CLAIMED',
            'ranking': 'unique source locations in tool traversal order; not causal confidence'}


async def stdio_solve(steps, *, max_calls=32, budget_s=110):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import os
    env = {k: v for k, v in os.environ.items() if k != 'RVW_MCP_PLUGINS'}
    params = StdioServerParameters(command=sys.executable, args=['-m', 'rvw', 'mcp'], env=env)
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            async def call(tool, arguments):
                response = await session.call_tool(tool, arguments)
                if getattr(response, 'is_error', getattr(response, 'isError', False)):
                    raise RuntimeError(response.content[0].text)
                return json.loads(response.content[0].text)
            return await solve(call, steps, max_calls=max_calls, budget_s=budget_s)


def run(plan, out, *, max_calls=32, budget_s=110):
    plan = json.loads(Path(plan).read_text())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    async def execute():
        return await stdio_solve(plan['steps'], max_calls=max_calls, budget_s=budget_s)
    result = anyio.run(execute)
    if 'truth' in plan:
        result['true_line_rank'] = rank(result['candidates'], plan['truth']['file'], plan['truth']['line'])
    (out / 'solver.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
