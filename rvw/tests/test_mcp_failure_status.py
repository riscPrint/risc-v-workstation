"""A completed request must retain its negative evidence status."""
import pytest
from rvw.mcp.envelope import envelope

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('verdict', ['fail', 'error', 'inconclusive', 'unsupported', 'not_installed'])
def test_negative_verdict_is_not_ok(verdict):
    result = envelope({'verdict': verdict})
    assert result['status'] == verdict
    assert result['verdict'] == verdict

def test_legacy_c4_reject_is_not_ok():
    result = envelope({'schema': 'rvw.verdict/2', 'verdict': 'reject'})
    assert result['status'] == 'fail'
    assert result['legacy_verdict'] == 'reject'

def test_completed_job_keeps_lifecycle_state_and_failed_result():
    result = envelope({'status': 'done', 'result': {'verdict': 'fail'}})
    assert result['status'] == 'done'
    assert result['result']['verdict'] == 'fail'

def test_ungraded_completion_has_no_pass():
    result = envelope({'count': 3})
    assert result['status'] == 'ok'
    assert 'verdict' not in result

def test_expected_job_error_has_no_traceback():
    from rvw.mcp.jobs import JobManager
    from rvw.mcp.spec import ToolError
    manager = JobManager()
    def reject(job):
        raise ToolError('Supply a trace with retirements.', code='invalid_input')
    try:
        job = manager.submit('test_input', {}, reject)
        assert job.done.wait(5)
        assert job.status == 'failed'
        assert 'Supply a trace' in '\n'.join(job.tail(10))
        assert 'Traceback' not in '\n'.join(job.tail(10))
    finally:
        manager.shutdown()
