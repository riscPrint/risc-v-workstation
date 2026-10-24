"""A CLI stop must unwind through the adapter process-group and lock cleanup."""
import os
import signal
import subprocess
import sys
import time

import pytest

from rvw.common.lock import status


def _tree(root):
    rows = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,pgid='], text=True)
    children = {}
    for row in rows.splitlines():
        pid, ppid, pgid = map(int, row.split())
        children.setdefault(ppid, []).append((pid, pgid))
    found, todo = {}, [root]
    while todo:
        for pid, pgid in children.get(todo.pop(), []):
            found[pid] = pgid
            todo.append(pid)
    return found


def _alive(pid):
    state = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith('Z')


@pytest.mark.parametrize('sig', [signal.SIGTERM, signal.SIGHUP])
def test_cli_signal_stops_adapter_and_releases_lock(fake, tmp_path, sig):
    fake.prog('rv64ui-p-add', 'status=pass sleep=60')
    log = tmp_path / 'cli.log'
    command = [sys.executable, '-m', 'rvw', 'regress', 'run', '--core', str(fake.config),
               '--tier', 'quick', '--filter', '^rv64ui-p-add$', '--out', str(tmp_path / 'out'),
               '--no-cache']
    owned = {}
    with log.open('w') as stream:
        process = subprocess.Popen(command, env=os.environ.copy(), stdout=stream,
                                   stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 30
            while not (fake.log.exists() and 'run rv64ui-p-add ' in fake.log.read_text()):
                assert process.poll() is None, log.read_text()
                assert time.monotonic() < deadline, log.read_text()
                time.sleep(0.05)
            owned = _tree(process.pid)
            assert owned, 'adapter process was not running'
            assert status('fake-test', tmp_path / 'locks')['held'], 'adapter lock was not held'
            process.send_signal(sig)
            code = process.wait(timeout=12)
            assert not any(_alive(pid) for pid in owned), owned
            assert not status('fake-test', tmp_path / 'locks')['held']
            assert code == 128 + sig
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for pgid in set(owned.values()):
                if pgid != os.getpgrp():
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
