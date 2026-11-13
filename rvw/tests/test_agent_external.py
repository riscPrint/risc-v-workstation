"""Actual external clients over MCP. No LLM calls and no native RTL."""
import json
import sys
from pathlib import Path

import pytest

from rvw.agent_bench.external import run_trial

pytestmark = pytest.mark.fast
PACK = Path(__file__).resolve().parents[2] / 'examples/agent-bench/tasks.json'
CLIENT = [sys.executable, '-m', 'rvw.agent_bench.external_client']


def test_external_scripted_client_repeats_over_mcp_and_never_sees_evaluator(tmp_path):
    report = run_trial(PACK, 'task-03', CLIENT, tmp_path / 'good', budget_s=20, repeats=2,
                       model='scripted MCP harness baseline')
    assert report['summary']['tasks'] == report['summary']['correct_fixes'] == 2
    assert report['summary']['detected'] == 2
    assert report['native_validation'] == 'NOT RUN'
    assert report['track'] == 'fixture'
    assert all(a['complete'] and not a['timed_out'] and a['calls'] == 5 for a in report['attempts'])
    assert len(report['task_pack_sha256']) == len(report['task_sha256']) == 64
    assert report['machine']['python']
    assert not list((tmp_path / 'good/trial-1').glob('*pack*'))
    assert 'private' not in json.dumps(report['attempts'])


def test_external_careless_client_cannot_self_award_a_fix(tmp_path):
    report = run_trial(PACK, 'task-03', CLIENT + ['careless'], tmp_path / 'bad', budget_s=20)
    assert report['summary']['false_fixes'] == 1
    assert report['summary']['correct_fixes'] == 0
    assert report['summary']['detected'] == 0



def test_external_tool_budget_stops_scoring_after_inspect(tmp_path):
    report = run_trial(PACK, 'task-03', CLIENT, tmp_path / 'budget', max_calls=1, budget_s=20)
    assert report['attempts'][0]['calls'] == 1
    assert report['attempts'][0]['budget_rejections'] == 1
    assert not report['attempts'][0]['complete']
    assert report['summary']['correct_fixes'] == 0


def test_missing_client_executable_retains_an_incomplete_attempt(tmp_path):
    report = run_trial(PACK, 'task-03', ['/no/such/agent-client'], tmp_path / 'missing')
    assert report['attempts'][0]['exit_code'] is None
    assert report['summary']['censored_root_causes'] == 1
    assert report['summary']['false_fix_rate'] is None
