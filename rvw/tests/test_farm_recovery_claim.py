import pytest

from rvw.farm.service import Queue

pytestmark = pytest.mark.fast


def test_stale_recovery_preserves_a_new_claim(tmp_path, monkeypatch):
    queue, other = Queue(tmp_path), Queue(tmp_path)
    job = queue.submit('alice', ['true'], retries=2)
    queue.claim()
    queue.update(job['id'], controller=2147483647, heartbeat=0)
    read_jobs = queue.jobs

    def recover_and_reclaim_after_read(owner=None):
        snapshot = read_jobs(owner)
        assert other.recover()[0]['state'] == 'queued'
        assert len(other.claim()['attempts']) == 2
        return snapshot

    monkeypatch.setattr(queue, 'jobs', recover_and_reclaim_after_read)
    assert queue.recover() == []
    stored = other.jobs()[0]
    assert stored['state'] == 'running'
    assert [a['status'] for a in stored['attempts']] == ['infrastructure_error', 'running']
    assert other.claim() is None
