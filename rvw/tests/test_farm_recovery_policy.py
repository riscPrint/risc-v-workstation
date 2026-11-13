import pytest

from rvw.farm.service import Queue

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('retry_on,expected', [([], 'inconclusive'), (['error'], 'inconclusive'), (['infrastructure_error'], 'queued')])
def test_crash_recovery_respects_retry_policy(tmp_path, retry_on, expected):
    queue = Queue(tmp_path)
    queue.submit('owner', ['true'], retries=1, retry_on=retry_on)
    job = queue.claim()
    queue.update(job['id'], controller=2147483647, heartbeat=0)
    recovered = queue.recover()
    assert recovered[0]['state'] == expected
    assert recovered[0]['attempts'][0]['status'] == 'infrastructure_error'
