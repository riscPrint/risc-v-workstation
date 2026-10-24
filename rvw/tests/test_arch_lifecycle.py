"""Use the real C1 supervisor with a fixture child that ignores termination."""
import os
from pathlib import Path
import signal
import sys
import time

import pytest

from rvw.arch import core, mcp_tools
from rvw.common.lock import _busy_file
from rvw.mcp.jobs import JobManager
from rvw.mcp.worker import run_function


def child_command(tmp_path, monkeypatch):
    locks = tmp_path / 'locks'
    monkeypatch.setenv('RVW_LOCK_DIR', str(locks))
    pid_file = tmp_path / 'child.pid'
    child = tmp_path / 'child.py'
    child.write_text('import os,signal,time\nfrom pathlib import Path\n'
                     'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                     f'Path({str(pid_file)!r}).write_text(str(os.getpid()))\n'
                     'time.sleep(120)\n')
    return ([sys.executable, '-m', 'rvw.common.lock', 'arch-lifecycle', sys.executable,
             str(core.ROOT / 'RiscvSim/scripts/supervise.py'), sys.executable, str(child)],
            pid_file, locks / 'arch-lifecycle.flock')


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def wait_child(path):
    deadline = time.monotonic() + 10
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(.1)
    assert path.exists(), 'fixture child did not start'
    return int(path.read_text())


def cleanup(path):
    if path.exists():
        try:
            os.kill(int(path.read_text()), signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_c1_timeout_stops_supervised_child_and_releases_lock(tmp_path, monkeypatch):
    command, pid, lock = child_command(tmp_path, monkeypatch)
    try:
        with pytest.raises(core.ArchError, match='124'):
            core.invoke(command, tmp_path / 'run.log', timeout=2, grace=core.C1_GRACE_S)
        assert pid.exists()
        assert not alive(int(pid.read_text()))
        assert not _busy_file(lock)
    finally:
        cleanup(pid)


@pytest.mark.parametrize("stop", ["cancel", "shutdown"])
def test_mcp_cancel_waits_for_c1_cleanup(tmp_path, monkeypatch, stop):
    command, pid, lock = child_command(tmp_path, monkeypatch)
    # Exercise the architecture handler and its real isolated worker. Select a
    # single invoke operation instead of a complete calibration fixture.
    def invoke_worker(job, module, function, arguments):
        return run_function(job, 'rvw.arch.core', 'invoke', {
            'command': command, 'log': str(tmp_path / 'run.log'), 'timeout': 120,
            'grace': core.C1_GRACE_S})
    monkeypatch.setattr(mcp_tools, 'run_function', invoke_worker)
    manager = JobManager()
    try:
        job = manager.submit('arch_calibrate', {}, mcp_tools.handler('rvw.arch.cli', 'calibrate'))
        child_pid = wait_child(pid)
        assert _busy_file(lock)
        if stop == 'cancel':
            job.request_cancel()
        else:
            manager.shutdown()
        assert job.done.wait(35)
        assert job.status == 'cancelled'
        assert not alive(child_pid)
        assert not _busy_file(lock)
    finally:
        manager.shutdown()
        cleanup(pid)
