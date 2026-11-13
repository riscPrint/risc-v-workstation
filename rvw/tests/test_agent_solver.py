"""The solver ranks tool outputs only and retains failed workflow steps."""
import anyio
import pytest
from rvw.agent_bench.solver import WORKFLOW, locations, rank, solve

pytestmark = pytest.mark.fast


def test_candidates_keep_tool_order_and_require_full_source_suffix():
    candidates = locations({'assignments': [{'loc': '/core/src/A.scala:3'}, {'loc': '/core/src/B.scala:4'},
                                            {'loc': '/core/src/A.scala:3'}]})
    assert rank(candidates, 'src/B.scala', 4) == 2
    assert rank(candidates, 'wrong/B.scala', 4) is None
    assert rank(candidates, 'src/B.scala', 5) is None


def test_workflow_waits_for_jobs_and_retains_tool_failures():
    calls = []
    async def call(tool, arguments):
        calls.append((tool, arguments))
        if tool == 'regress_run':
            return {'status': 'running', 'job_id': 'one'}
        if tool == 'job_status':
            return {'status': 'done', 'job_id': 'one', 'result': {'status': 'fail'}}
        if tool == 'wave_why':
            raise RuntimeError('wave missing')
        if tool == 'query_drivers':
            return {'assignments': [{'loc': 'src/Core.scala:12'}]}
        return {}
    result = anyio.run(lambda: solve(call, [{'tool': t, 'arguments': {}} for t in WORKFLOW]))
    assert result['status'] == 'inconclusive' and result['calls'] == 6
    assert result['candidates'] == ['src/Core.scala:12']
    assert result['transcript'][-1]['error'] == 'wave missing'
    assert calls[1] == ('job_status', {'job_id': 'one', 'wait_s': 30})
    assert result['repair'] == 'NOT CLAIMED'


def test_budget_and_timeout_cannot_earn_complete_result():
    async def call(tool, arguments):
        await anyio.sleep(1)
    result = anyio.run(lambda: solve(call, [{'tool': t, 'arguments': {}} for t in WORKFLOW], budget_s=0.01))
    assert result['timed_out'] and result['status'] == 'inconclusive'
    async def quick(tool, arguments):
        return {}
    result = anyio.run(lambda: solve(quick, [{'tool': t, 'arguments': {}} for t in WORKFLOW], max_calls=1))
    assert result['calls'] == 1 and result['status'] == 'inconclusive'


def test_real_stdio_workflow_preserves_missing_native_inputs(tmp_path):
    from rvw.agent_bench.solver import stdio_solve
    steps = [
        {'tool': 'regress_run', 'arguments': {'project': str(tmp_path / 'missing.toml'), 'tier': 'quick'}},
        {'tool': 'cosim_check', 'arguments': {'trace': str(tmp_path / 'missing.jsonl'), 'elf': str(tmp_path / 'missing.elf')}},
        {'tool': 'bundle_make', 'arguments': {'run_dir': str(tmp_path / 'missing-run'), 'no_rerun': True}},
        {'tool': 'query_drivers', 'arguments': {'db': str(tmp_path / 'missing.db'), 'signal': 'state'}},
        {'tool': 'wave_why', 'arguments': {'db': str(tmp_path / 'missing.db'), 'wave': str(tmp_path / 'missing.vcd'), 'signal': 'state', 'at': '1c'}},
    ]
    result = anyio.run(lambda: stdio_solve(steps, budget_s=30))
    assert result['status'] == 'inconclusive'
    assert result['candidates'] == []
    assert len(result['transcript']) == 5

def test_mismatch_order_selects_live_wave_time_and_observed_field():
    calls = []
    async def call(tool, arguments):
        calls.append((tool, dict(arguments)))
        if tool == 'cosim_check':
            return {'status': 'mismatch', 'mismatch': {'order': 7, 'differences': {'pc_next': {}}}}
        if tool == 'wave_find':
            assert arguments['expr'] == '(retire_order == 7) && (retire_valid == 1)'
            return {'first': 1234}
        if tool in ('query_drivers', 'wave_why'):
            assert arguments['signal'] == 'next_pc'
        if tool == 'wave_why':
            assert arguments['at'] == '1234'
        return {}
    steps = [{'tool': t, 'arguments': {}} for t in WORKFLOW]
    for step in steps[-2:]:
        step['mismatch_signals'] = {'pc_next': 'next_pc'}
    steps[-1]['arguments'] = {'wave': 'dut.fst', 'signal': 'default', 'at': '0'}
    steps[-1]['wave_time'] = {'order_signal': 'retire_order', 'valid_signal': 'retire_valid'}
    result = anyio.run(lambda: solve(call, steps))
    assert result['status'] == 'observed' and result['calls'] == 6
    assert result['transcript'][-1]['time_query']['result'] == {'first': 1234}
    assert calls[-2][0] == 'wave_find' and calls[-1][0] == 'wave_why'


def test_matching_prefix_uses_actual_wave_end_without_claiming_divergence():
    async def call(tool, arguments):
        if tool == 'cosim_check':
            return {'status': 'match', 'end_status': 'timeout', 'mismatch': None}
        if tool == 'wave_info':
            return {'end': 999}
        if tool == 'wave_why':
            assert arguments['at'] == '999'
        return {}
    steps = [{'tool': t, 'arguments': {}} for t in WORKFLOW]
    steps[-1].update(arguments={'wave': 'dut.fst'}, wave_time={'order_signal': 'order', 'valid_signal': 'valid'})
    result = anyio.run(lambda: solve(call, steps))
    assert result['status'] == 'observed'
    assert 'no architectural mismatch' in result['transcript'][-1]['time_basis']
    assert result['repair'] == 'NOT CLAIMED'


def test_missing_retirement_prevents_query_at_a_guessed_time():
    calls = []
    async def call(tool, arguments):
        calls.append(tool)
        if tool == 'cosim_check':
            return {'mismatch': {'order': 0}}
        if tool == 'wave_find':
            return {'first': None}
        return {}
    steps = [{'tool': t, 'arguments': {}} for t in WORKFLOW]
    steps[-1].update(arguments={'wave': 'dut.fst'}, wave_time={'order_signal': 'order', 'valid_signal': 'valid'})
    result = anyio.run(lambda: solve(call, steps))
    assert 'wave_why' not in calls
    assert result['status'] == 'inconclusive'
    assert 'absent' in result['transcript'][-1]['error']
