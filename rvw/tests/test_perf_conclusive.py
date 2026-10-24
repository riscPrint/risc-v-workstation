"""A numerical counter match cannot make an inconclusive C1 run reliable."""
import json

import pytest

from rvw.cli import main
from rvw.mcp.registry import Registry
from perf_fixtures import analyze

INCONCLUSIVE = [
    {"inconclusive": "input identity changed before result publication: adapter identity; rerun"},
    {"inconclusive": True}, {"synthesized": True}, {"wall_clock_timeout": True},
    {"status": "error"}, {"status": "assert", "details": {"concurrent": True}},
    {"status": "rvfi_error", "details": {"serial_rerun": {"attributed": False}}},
]


@pytest.fixture
def counter_trace(tmp_path):
    trace = tmp_path / 'konata.log'
    trace.write_text('Kanata\t0004\nC=\t0\nI\t0\t0\t0\nC\t1\nR\t0\t0\t0\n')
    counters = {"schema": "rvw.run/1", "status": "pass", "cycles": 2, "instret": 1,
                "artifacts": {"konata": "konata.log"}}
    return trace, counters


@pytest.mark.parametrize('extra', INCONCLUSIVE)
def test_inconclusive_counters_never_claim_a_match(counter_trace, extra):
    trace, counters = counter_trace
    counters.update(extra)
    (trace.parent / 'result.json').write_text(json.dumps(counters))
    with pytest.raises(ValueError, match='inconclusive'):
        analyze(trace)


@pytest.mark.parametrize('status', ['pass', 'fail', 'assert', 'rvfi_error', 'timeout'])
def test_conclusive_counter_cross_checks_remain_available(counter_trace, status):
    trace, counters = counter_trace
    counters['status'] = status
    (trace.parent / 'result.json').write_text(json.dumps(counters))
    cross_check = analyze(trace)['cross_check']
    assert cross_check['result_status'] == status
    assert cross_check['exact_counter_match']


def test_inconclusive_perf_cli_and_mcp_agree(counter_trace, capsys):
    trace, counters = counter_trace
    counters.update(INCONCLUSIVE[0])
    (trace.parent / 'result.json').write_text(json.dumps(counters))
    assert main(['perf', str(trace), '--json']) == 2
    error = capsys.readouterr().err.removeprefix('rvw perf: ').strip()
    assert 'inconclusive' in error and counters['inconclusive'] in error
    registry, problems = Registry.discover({'perf'})
    assert not problems
    try:
        _, started, failed = registry.call_json('perf_report', {'path': str(trace)})
        assert not failed, started
        _, job, failed = registry.call_json('job_status', {'job_id': started['job_id'], 'wait_s': 60})
        assert not failed and job['status'] == 'failed', job
        assert error in job['error']
    finally:
        registry.jobs.shutdown()
