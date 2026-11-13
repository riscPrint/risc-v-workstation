#!/usr/bin/env python3
"""Run native queue crash/retry and acknowledged cancellation controls.

Supply an adapter, manifest and new queue directory. Use private core copies,
private locks and nice priority. This runs one native shard at a time.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from rvw.farm.service import Queue, group_live
from rvw.results import write_json


def wait_running(queue, job_id, process):
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        job = next(j for j in queue.jobs() if j['id'] == job_id)
        if job.get('pgid') and group_live(job['pgid']):
            return job
        if process.poll() is not None:
            raise RuntimeError('worker exited before launch')
        time.sleep(.2)
    raise TimeoutError('worker did not launch')


def wait_native(queue, job_id, process):
    deadline = time.monotonic()+600
    while time.monotonic() < deadline:
        for path in (queue.root/job_id).glob('attempt-*/cells/*/result.json'):
            run = json.loads(path.read_text())
            pid = run.get('details', {}).get('simulation_session', {}).get('process_id')
            if pid and group_live(int(pid)):
                return int(pid)
        if process.poll() is not None:
            raise RuntimeError('worker exited before a native C1 result')
        time.sleep(.2)
    raise TimeoutError('no live native simulation session')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--adapter', required=True)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    queue = Queue(args.root)
    command = ['nice', '-n', '10', sys.executable, '-m', 'rvw.farm.native_shard',
               '--manifest', str(Path(args.manifest).resolve()), '--adapter', args.adapter,
               '--out', '{attempt_dir}']
    worker = [sys.executable, '-c', 'import sys; from rvw.farm.service import Queue; Queue(sys.argv[1]).work_once()', str(queue.root)]
    crashed = queue.submit('native', command, retries=1, timeout=660)
    process = subprocess.Popen(worker, start_new_session=True)
    active = wait_running(queue, crashed['id'], process)
    crashed_native_pid = wait_native(queue, crashed['id'], process)
    os.kill(process.pid, signal.SIGKILL)
    process.wait(timeout=10)
    recovered = queue.recover(stale_after=0)
    assert len(recovered) == 1 and recovered[0]['state'] == 'queued', recovered
    assert not group_live(active['pgid'])
    assert not group_live(crashed_native_pid)
    retried = queue.work_once()
    assert retried['state'] == 'complete', retried
    assert [a['status'] for a in retried['attempts']] == ['infrastructure_error', 'complete']
    cancelled = queue.submit('native', command, timeout=660)
    process = subprocess.Popen(worker, start_new_session=True)
    active = wait_running(queue, cancelled['id'], process)
    cancelled_native_pid = wait_native(queue, cancelled['id'], process)
    assert queue.cancel(cancelled['id'], 'native')['state'] == 'cancel_requested'
    process.wait(timeout=30)
    final = next(j for j in queue.jobs() if j['id'] == cancelled['id'])
    assert final['state'] == 'cancelled', final
    assert not group_live(active['pgid'])
    assert not group_live(cancelled_native_pid)
    write_json(queue.root/'controls.json', dict(crash_recovery=recovered, retry=retried,
               cancellation=final, crashed_native_pid=crashed_native_pid,
               cancelled_native_pid=cancelled_native_pid, cancelled_group_live=False, native_groups_live=False))


if __name__ == '__main__':
    main()
