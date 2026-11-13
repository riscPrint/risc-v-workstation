import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('coherence_fair', Path(__file__).resolve().parents[2] / 'SpinalChecks/coherence/fair.py')
fair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fair)


def test_weak_fairness_rejects_scheduler_starvation_but_not_a_fair_retry_cycle():
    graph = {0: [('retry', 0), ('grant', 1)], 1: []}
    assert fair.fair_cycle(graph, lambda s: s == 0, {'arbitration': {'grant'}}) is None
    assert fair.fair_cycle(graph, lambda s: s == 0, {'environment': {'retry'}}) is not None


def test_disabled_action_can_be_weakly_fair_without_ever_running():
    graph = {0: [('retry', 1), ('grant', 2)], 1: [('retry', 0)], 2: []}
    assert fair.fair_cycle(graph, lambda s: s != 2, {'arbitration': {'grant'}}) is not None


def test_deadlock_and_budget_are_distinct_from_exhausted_progress():
    run = lambda succ, limit=10: fair.explore(0, succ, lambda s: None, lambda s: s == 2,
        {'request-0': lambda s: s != 2}, {'response': {'grant'}}, limit)
    assert run(lambda s: [('grant', s+1)])['status'] == 'pass'
    assert run(lambda s: [])['failure'] == 'fair_noncompletion'
    assert run(lambda s: [('grant', s+1)], 1)['status'] == 'inconclusive'


def test_per_request_targets_do_not_hide_starvation_with_unrelated_completions():
    graph = {0: [('other-complete', 1)], 1: [('other-complete', 0)]}
    result = fair.explore(0, lambda s: graph[s], lambda s: None, lambda s: False,
                          {'hart0-request': lambda s: True}, {'other-response': {'other-complete'}})
    assert result['status'] == 'fail' and result['target'] == 'hart0-request'


def test_existing_coherence_model_with_named_fairness():
    import json
    import subprocess
    import sys
    from rvw.common.proc import run_group
    root = Path(__file__).resolve().parents[2]
    for bug, status in [(None, 'pass'), ('retry', 'fail'), ('lost_ack', 'fail'), ('stale_data', 'fail')]:
        command = [sys.executable, str(root / 'SpinalChecks/coherence/model.py'), '--fair']
        if bug:
            command += ['--bug', bug]
        result = run_group(command, timeout=15, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        report = json.loads(result.stdout)
        assert report['status'] == status
        assert report['fairness'] and not report['exhaustive_rtl_proof']
        assert result.returncode == (0 if status == 'pass' else 1)
