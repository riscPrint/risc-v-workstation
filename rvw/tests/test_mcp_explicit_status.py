import pytest
from rvw.mcp.envelope import envelope

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('verdict', ['fail', 'error', 'inconclusive', 'unsupported', 'not_installed', 'no_checks'])
def test_negative_verdict_overrides_completion_ok(verdict):
    assert envelope({'status': 'ok', 'verdict': verdict})['status'] == verdict


def test_c4_reject_overrides_completion_ok():
    result = envelope({'schema':'rvw.verdict/2', 'status':'ok', 'verdict':'reject'})
    assert result['status']=='fail'


def test_job_lifecycle_state_is_preserved():
    assert envelope({'status':'done', 'result':{'verdict':'fail'}})['status']=='done'
