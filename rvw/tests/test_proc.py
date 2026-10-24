import os
import signal
import subprocess
import sys
import time

import pytest

from rvw.common.proc import TIMEOUT_EXIT, run_group

CHILD = "import os,sys,time; open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(30); open(sys.argv[2],'w').write('x')"
PARENT = ("import subprocess,sys; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]]);"
          " import time; time.sleep(30)")


def _alive(pid):
    """Running, not a zombie waiting to be reaped by launchd/init."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return bool(r.stdout.strip()) and not r.stdout.strip().startswith("Z")


def test_timeout_stops_grandchildren(tmp_path):
    pidf, marker = tmp_path / "pid", tmp_path / "done"
    # 4 s: two Python start-ups under a loaded test run must fit before the timeout fires.
    r = run_group([sys.executable, "-c", PARENT, CHILD, str(pidf), str(marker)], timeout=4, grace=1)
    assert r.timed_out and r.returncode == TIMEOUT_EXIT
    assert pidf.exists(), "the grandchild did not start before the timeout"
    pid = int(pidf.read_text())
    for _ in range(50):
        if not _alive(pid):
            break
        time.sleep(0.1)
    assert not _alive(pid) and not marker.exists()


def test_normal_exit_and_capture():
    r = run_group([sys.executable, "-c", "print('hi'); raise SystemExit(3)"], capture=True)
    assert r.returncode == 3 and r.stdout.strip() == "hi" and not r.timed_out


# Review 12: a group member that keeps stdout open must not delay the result or turn a finished
# run into a timeout; it is stopped when the leader exits.
HOLDER = ("import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('ready'); time.sleep(3);"
          " pathlib.Path(sys.argv[2]).write_text('survived')")
LEADER = ("import pathlib,subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]])\n"
          "while not pathlib.Path(sys.argv[2]).exists(): time.sleep(.01)\n"
          "print('leader exiting', flush=True)")


def test_leader_exit_ends_the_run_while_a_member_holds_stdout(tmp_path):
    for timeout in (10, None):
        ready, marker = tmp_path / f"ready-{timeout}", tmp_path / f"survived-{timeout}"
        t = time.monotonic()
        r = run_group([sys.executable, "-c", LEADER, HOLDER, str(ready), str(marker)], capture=True,
                      timeout=timeout, grace=0.1)
        took = time.monotonic() - t
        assert r.returncode == 0 and not r.timed_out, (timeout, r)
        assert r.stdout == "leader exiting\n"
        assert took < 2.5, f"waited {took:.1f}s for a member holding stdout"
        time.sleep(3.5)
        assert ready.exists() and not marker.exists(), "the member outlived the leader"


ESCAPEE = ("import os,sys,time; os.setsid(); open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(20)")
ESCAPE_LEADER = ("import os,subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]])\n"
                 "while not os.path.exists(sys.argv[2]) or not open(sys.argv[2]).read(): time.sleep(.01)\n"
                 "print('done', flush=True)")


def test_drain_is_bounded_when_a_process_outside_the_group_holds_stdout(tmp_path):
    pidf = tmp_path / "pid"
    t = time.monotonic()
    r = run_group([sys.executable, "-c", ESCAPE_LEADER, ESCAPEE, str(pidf)], capture=True, timeout=15)
    took = time.monotonic() - t
    try:
        assert r.returncode == 0 and not r.timed_out and r.stdout == "done\n"
        assert took < 8, f"drained for {took:.1f}s"
    finally:
        try:
            os.kill(int(pidf.read_text()), 9)
        except (OSError, ValueError):
            pass


def test_input_and_large_output():
    prog = "import sys; d=sys.stdin.read(); sys.stdout.write(d.upper()*2000); sys.stderr.write('e\\r\\n')"
    r = run_group([sys.executable, "-c", prog], capture=True, input="abcdefghij" * 10, timeout=30)
    assert r.returncode == 0 and not r.timed_out
    assert r.stdout == ("ABCDEFGHIJ" * 10) * 2000 and r.stderr == "e\n"
    rb = run_group([sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes(range(256)))"],
                   capture=True, text=False)
    assert rb.stdout == bytes(range(256))


def test_timeout_with_capture_keeps_the_output_so_far():
    prog = "import time; print('started', flush=True); time.sleep(30)"
    t = time.monotonic()
    r = run_group([sys.executable, "-c", prog], capture=True, timeout=2, grace=0.2)
    assert r.timed_out and r.returncode == TIMEOUT_EXIT and r.stdout == "started\n"
    assert time.monotonic() - t < 6


# Review 15: cancellation can arrive before Popen returns or inside _Pipes.__init__.
@pytest.mark.parametrize('stage', ['spawn', 'pipes'])
@pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_cancellation_during_setup_stops_the_child(stage, sig, monkeypatch):
    from rvw.common import proc
    children = []
    real_popen, real_pipes = proc.subprocess.Popen, proc._Pipes
    def spawn(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        if stage == 'spawn':
            os.kill(os.getpid(), sig)
        return child
    def pipes(*args, **kwargs):
        os.kill(os.getpid(), sig)
        return real_pipes(*args, **kwargs)
    def interrupt(signum, frame):
        raise KeyboardInterrupt('cancel during setup')
    old = signal.signal(sig, interrupt)
    monkeypatch.setattr(proc.subprocess, 'Popen', spawn)
    if stage == 'pipes':
        monkeypatch.setattr(proc, '_Pipes', pipes)
    try:
        with pytest.raises(KeyboardInterrupt, match='cancel during setup'):
            proc.run_group([sys.executable, '-c', 'import time; time.sleep(60)'], capture=True, grace=0.1)
        assert len(children) == 1
        assert children[0].poll() is not None, 'child survived setup cancellation'
        assert all(getattr(children[0], n).closed for n in ('stdout', 'stderr'))
    finally:
        signal.signal(sig, old)
        for child in children:
            proc.kill_group(child, grace=0.1)
            for name in ('stdout', 'stderr'):
                getattr(child, name).close()


@pytest.mark.parametrize('stage', ['create', 'register'])
def test_pipe_setup_error_closes_selector_and_child(monkeypatch, stage):
    from rvw.common import proc
    children, selectors = [], []
    real_popen = proc.subprocess.Popen
    real_selector = proc.selectors.DefaultSelector
    def spawn(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child
    def selector():
        if stage == 'create':
            raise RuntimeError('pipe registration failed')
        sel = real_selector()
        selectors.append(sel)
        def fail(*args, **kwargs):
            raise RuntimeError('pipe registration failed')
        monkeypatch.setattr(sel, 'register', fail)
        return sel
    monkeypatch.setattr(proc.subprocess, 'Popen', spawn)
    monkeypatch.setattr(proc.selectors, 'DefaultSelector', selector)
    try:
        with pytest.raises(RuntimeError, match='pipe registration failed'):
            proc.run_group([sys.executable, '-c', 'import time; time.sleep(60)'], capture=True, grace=0.1)
        assert children[0].poll() is not None
        assert all(sel.get_map() is None for sel in selectors)
        assert all(getattr(children[0], n).closed for n in ('stdout', 'stderr'))
    finally:
        for child in children:
            proc.kill_group(child, grace=0.1)
        for sel in selectors:
            sel.close()


@pytest.mark.parametrize('term_denied', [False, True])
def test_kill_group_kills_members_after_leader_exit(monkeypatch, term_denied):
    from rvw.common import proc
    calls = []
    class ExitedLeader:
        pid = 123
        def wait(self, timeout):
            return 0
    def killpg(pid, sig):
        calls.append(sig)
        if sig == signal.SIGTERM and term_denied:
            raise PermissionError()
    monkeypatch.setattr(proc.os, 'killpg', killpg)
    proc.kill_group(ExitedLeader(), grace=0.1)
    assert calls == [signal.SIGTERM, signal.SIGKILL]
