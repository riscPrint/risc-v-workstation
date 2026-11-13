"""Benchmark evaluator tests. No external LLM or native RTL tools."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from rvw.agent_bench.engine import EXPRESSIONS, Session, load_pack, report, scripted
from rvw.mcp.spec import ToolError

PACK = Path(__file__).resolve().parents[2] / 'examples/agent-bench/tasks.json'


def test_ten_tasks_and_hidden_oracle():
    tasks, digest = load_pack(PACK)
    assert len(tasks) == 10 and len(digest) == 64
    for task in tasks:
        session = Session(task)
        registry = session.registry()
        try:
            public = registry.call('bench_inspect', {})
            assert 'private' not in public and 'vectors' not in json.dumps(public)
            public['statements'].clear()
            assert session.task['public']['statements']
            scripted(registry.call)
            score = session.score()
            assert score['correct_fix'] and not score['false_fix']
            assert score['time_to_root_cause_s'] is not None
            assert score['detected'] == score['defects']
        finally:
            registry.jobs.shutdown()


def test_careless_repair_and_stale_evidence():
    tasks, digest = load_pack(PACK)
    scores = []
    for task in tasks:
        s = Session(task)
        r = s.registry()
        try:
            scripted(r.call, careless=True)
            scores.append(s.score())
        finally:
            r.jobs.shutdown()
    result = report(scores, digest, 'careless')['summary']
    assert result['correct_fixes'] == 0 and result['false_fixes'] == 10
    assert result['detected'] == 0 and result['misleading_evidence'] == 6
    assert sum(s['root_cause_censored'] for s in scores) == 6


def test_schema_and_tool_boundary():
    s = Session(load_pack(PACK)[0][0])
    r = s.registry()
    try:
        for tool, args in [('query_read', {'path': str(PACK)}),
                           ('bench_inspect', {'private': True}),
                           ('bench_finish', {'claimed_fix': 'true'}),
                           ('bench_patch', {'statement': 's1', 'expression': '__import__("os")'})]:
            with pytest.raises(ToolError):
                r.call(tool, args)
        assert set(r.tools) == {'bench_inspect', 'bench_diagnose', 'bench_patch',
                                'bench_reject', 'bench_finish', 'job_status',
                                'job_log', 'job_cancel', 'job_list', 'job_result',
                                'job_events', 'rvw_tools_load', 'rvw_tools_search',
                                'rvw_tools_describe'}
        # Profile loading must stay inside this session's restricted catalog.
        assert r.call('rvw_tools_load', {'profile': 'all'})['added'] == []
        names = {t['name'] for t in r.call('rvw_tools_search', {'keyword': ''})['tools']}
        assert names == {'bench_inspect', 'bench_diagnose', 'bench_patch',
                         'bench_reject', 'bench_finish'}
        with pytest.raises(ToolError):
            r.call('query_read', {'path': str(PACK)})
    finally:
        r.jobs.shutdown()


def test_timing_rejection_and_final_candidate():
    task = load_pack(PACK)[0][2]
    ticks = iter(range(20))
    s = Session(task, clock=lambda: next(ticks))
    s.diagnose('s1', ['wave-old'])
    s.diagnose('s0', ['run'])
    s.diagnose('s1', ['run'])
    s.reject('wave-old', 'elf_sha256')
    s.reject('run', 'rtl_sha256')
    s.patch('s1', EXPRESSIONS['and'])
    s.patch('s1', 'U(0, 32 bits)')
    s.finish(True)
    score = s.score()
    assert score['time_to_root_cause_s'] == 3
    assert score['detected'] == 0 and score['false_rejections'] == 2
    assert score['false_fix']
    with pytest.raises(ToolError, match='finished'):
        s.inspect()


def test_incomplete_and_budget():
    s = Session(load_pack(PACK)[0][0], max_calls=1)
    s.inspect()
    with pytest.raises(ToolError, match='budget'):
        s.finish(True)
    score = s.score()
    assert not score['complete'] and not score['correct_fix']
    summary = report([score], 'x', 'none')['summary']
    assert summary['false_fix_rate'] is None


def test_dry_run_retains_results(tmp_path):
    from rvw.cli import main
    out = tmp_path / 'run'
    assert main(['agent-bench', 'dry-run', '--pack', str(PACK), '--out', str(out)]) == 0
    data = json.loads((out / 'results.json').read_text())
    assert data['track'] == 'fixture' and data['native_validation'] == 'NOT RUN'
    assert data['summary']['correct_fixes'] == 10
    assert len(data['tasks'][0]['transcript']) == 4
    with pytest.raises(FileExistsError):
        main(['agent-bench', 'dry-run', '--pack', str(PACK), '--out', str(out)])


def test_stdio_client(tmp_path):
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    out = tmp_path / 'stdio'

    async def run():
        params = StdioServerParameters(command=sys.executable,
            args=['-m', 'rvw.cli', 'agent-bench', 'serve', '--pack', str(PACK),
                  '--task', 'task-03', '--out', str(out)], env=dict(os.environ))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                assert 'bench_inspect' in names and 'regress_run' not in names
                async def call(name, arguments):
                    response = await client.call_tool(name, arguments)
                    assert not getattr(response, 'is_error', getattr(response, 'isError', False))
                    return json.loads(response.content[0].text)
                task = await call('bench_inspect', {})
                assert 'private' not in task
                await call('bench_reject', {'artifact': 'wave-old', 'reason': 'rtl_sha256'})
                await call('bench_diagnose', {'statement': 's1', 'evidence': ['run']})
                await call('bench_patch', {'statement': 's1', 'expression': EXPRESSIONS['and']})
                await call('bench_finish', {'claimed_fix': True})
    asyncio.run(run())
    data = json.loads((out / 'results.json').read_text())
    assert data['summary']['correct_fixes'] == 1
    assert data['summary']['detected'] == 1


def test_interrupted_run_keeps_full_denominator(tmp_path, monkeypatch):
    from rvw.agent_bench import cli
    from rvw.cli import main

    def stop(call, careless=False):
        raise RuntimeError('scripted client disconnected')
    monkeypatch.setattr(cli, 'scripted', stop)
    out = tmp_path / 'partial'
    with pytest.raises(RuntimeError, match='disconnected'):
        main(['agent-bench', 'dry-run', '--pack', str(PACK), '--out', str(out)])
    result = json.loads((out / 'results.json').read_text())
    assert result['summary']['tasks'] == 10
    assert result['summary']['censored_root_causes'] == 10
    assert all(not t['complete'] for t in result['tasks'])
