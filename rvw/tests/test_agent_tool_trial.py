"""External reference solver transport, with missing native inputs kept inconclusive."""
import json
import sys
from rvw.agent_bench.tool_trial import ToolSession, run_evidence_trial
from rvw.agent_bench.solver import WORKFLOW
import pytest

pytestmark = pytest.mark.fast


def test_public_tools_do_not_leak_truth_or_grant_source_repair():
    session = ToolSession({'id': 'unit', 'steps': [], 'budget_s': 30,
                           'truth': {'file': 'src/Secret.scala', 'line': 12}})
    assert 'truth' not in session.inspect()
    assert 'Secret' not in str(session.inspect())
    registry = session.registry()
    try:
        assert set(WORKFLOW) <= set(registry.tools)
        assert 'agent_bench_repair_check' not in registry.tools
        assert 'query_build_db' not in registry.tools
        session.requests = [{'tool': 'query_drivers', 'result': {'assignments': [{'loc': '/core/src/Secret.scala:12'}]}}]
        session.finish(True)
        result = session.score()
        assert result['true_line_rank'] == 1
        assert result['false_fix'] and not result['correct_fix']
        assert result['root_cause_censored']
    finally:
        registry.jobs.shutdown()


def test_scripted_solver_over_external_mcp_keeps_missing_evidence(tmp_path):
    plan = {'id': 'missing', 'steps': [
        {'tool': 'regress_run', 'arguments': {'project': str(tmp_path / 'missing.toml'), 'tier': 'quick'}},
        {'tool': 'cosim_check', 'arguments': {'trace': str(tmp_path / 'missing.jsonl'), 'elf': str(tmp_path / 'missing.elf')}},
        {'tool': 'bundle_make', 'arguments': {'run_dir': str(tmp_path / 'missing-run'), 'no_rerun': True}},
        {'tool': 'query_drivers', 'arguments': {'db': str(tmp_path / 'missing.db'), 'signal': 'state'}},
        {'tool': 'wave_why', 'arguments': {'db': str(tmp_path / 'missing.db'), 'wave': str(tmp_path / 'missing.vcd'), 'signal': 'state', 'at': '1c'}},
    ], 'truth': {'file': 'src/Private.scala', 'line': 4}}
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(plan))
    result = run_evidence_trial(path, [sys.executable, '-m', 'rvw.agent_bench.solver_client'],
                                tmp_path / 'trial', budget_s=30, max_calls=32)
    assert result['track'] == 'native-tools'
    assert result['summary']['correct_fixes'] == 0
    assert result['summary']['false_fixes'] == 0
    assert result['attempts'][0]['complete']
    assert result['attempts'][0]['calls'] >= 7
    assert 'Private.scala' not in json.dumps(result['attempts'][0]['requests'])
