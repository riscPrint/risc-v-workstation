import pytest

from rvw.farm.service import Queue

pytestmark = pytest.mark.fast


def test_cancel_does_not_acknowledge_a_concurrent_claim(tmp_path, monkeypatch):
    queue = Queue(tmp_path)
    worker = Queue(tmp_path)
    job = queue.submit('alice', ['true'])
    read_jobs = queue.jobs

    def claim_after_read(owner=None):
        snapshot = read_jobs(owner)
        if owner == 'alice':
            assert worker.claim()['id'] == job['id']
        return snapshot

    # Inject the worker claim after a cancellation snapshot has been read.
    # A cancellation that reads under its write transaction has no such window.
    monkeypatch.setattr(queue, 'jobs', claim_after_read)
    result = queue.cancel(job['id'], 'alice')
    stored = worker.jobs()[0]
    assert result['state'] == stored['state']
    if stored['attempts']:
        assert stored['state'] == 'cancel_requested'
        assert stored['attempts'][-1]['status'] == 'running'
    else:
        assert stored['state'] == 'cancelled'
        assert worker.claim() is None
