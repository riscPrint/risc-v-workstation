"""The machine-wide heavy-job lock (rvw.common.lock, scripts/with-lock.sh): one flock-based
implementation, one re-entry protocol, arrival order, and lifetime tied to the job's processes.
Reproductions from lock regressions (sigtest.sh, stale-race, nesting)."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from rvw.common import lock
from rvw.common.proc import run_group
from race_injection import race_injector

REPO = Path(__file__).resolve().parents[2]
WITH_LOCK = REPO / "scripts" / "with-lock.sh"


@pytest.fixture
def ld(tmp_path, monkeypatch):
    d = tmp_path / "locks"
    monkeypatch.setenv("RVW_LOCK_DIR", str(d))
    monkeypatch.delenv("RVW_LOCKS_HELD", raising=False)
    monkeypatch.delenv("RVW_LOCK_HELD", raising=False)
    monkeypatch.setenv("RVW_LOCK_POLL_S", "0.05")
    return d


def env(**extra):
    e = {k: v for k, v in os.environ.items() if k not in ("RVW_LOCKS_HELD", "RVW_LOCK_HELD")}
    e.update(extra)
    return e


def test_cancel_before_legacy_marker_never_publishes_empty_lock(ld, race_injector):
    paths = lock._Paths('startup', ld)

    def cancel():
        raise KeyboardInterrupt()

    injection = race_injector.at(Path, 'write_text', cancel, when='before')
    with pytest.raises(KeyboardInterrupt):
        lock._legacy_take(paths, 0.01, None)
    assert injection.fired
    assert not paths.legacy.exists()


def test_legacy_install_does_not_replace_empty_owner(ld, race_injector):
    paths = lock._Paths('startup', ld)

    def competing_owner():
        paths.legacy.mkdir()

    injection = race_injector.at(Path, 'write_text', competing_owner, when='before')
    def stop_wait(_):
        raise KeyboardInterrupt()
    race_injector.monkeypatch.setattr(lock.time, 'sleep', stop_wait)
    with pytest.raises(KeyboardInterrupt):
        lock._legacy_take(paths, 0.01, None)
    assert injection.fired
    assert paths.legacy.is_dir() and not paths.legacy.is_symlink()
    assert not list(paths.legacy.iterdir())


def held_now(name, d) -> bool:
    return lock.status(name, d)["held"]


def wait_for(cond, timeout=10.0, step=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(step)
    return False


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie (exited, not yet reaped) is not running.
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return bool(r.stdout.strip()) and not r.stdout.strip().startswith("Z")


# ------------------------------------------------------------------ lifetime (finding 18, O)

@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGKILL])
def test_killing_with_lock_kills_the_job_and_frees_the_lock(ld, tmp_path, sig):
    """sigtest.sh: killing the with-lock.sh process used to release the lock while the job ran."""
    p = subprocess.Popen([str(WITH_LOCK), "t", "sleep", "30"], env=env())
    assert wait_for(lambda: held_now("t", ld))
    p.send_signal(sig)
    p.wait(timeout=5)
    # The command is the with-lock.sh process (exec): nothing is left running, the lock is free.
    assert not alive(p.pid)
    r = subprocess.run([str(WITH_LOCK), "t", "echo", "second"], env=env(), capture_output=True, text=True,
                       timeout=10)
    assert r.stdout.strip() == "second"


def test_children_that_outlive_the_job_keep_the_lock(ld, tmp_path):
    """Killing only the job's leader (bash) leaves its child running: the child keeps the lock."""
    pidfile = tmp_path / "child.pid"
    p = subprocess.Popen([str(WITH_LOCK), "t", "bash", "-c", f"sleep 3 & echo $! > {pidfile}; wait"], env=env())
    assert wait_for(pidfile.exists)
    child = int(pidfile.read_text())
    os.kill(p.pid, signal.SIGKILL)
    p.wait(timeout=5)
    assert alive(child)
    assert held_now("t", ld)
    q = subprocess.Popen([str(WITH_LOCK), "t", "true"], env=env())
    time.sleep(1.0)
    assert q.poll() is None and alive(child), "second job ran while the first job's child still ran"
    assert q.wait(timeout=10) == 0
    assert not alive(child)


def test_run_group_children_keep_a_python_holders_lock(ld, tmp_path):
    """A Python holder killed while its run_group child runs: the child keeps the lock."""
    pidfile = tmp_path / "child.pid"
    code = textwrap.dedent(f"""
        from rvw.common.lock import held
        from rvw.common.proc import run_group
        with held("t", log=None):
            run_group(["bash", "-c", "echo $$ > {pidfile}; sleep 3"])
    """)
    p = subprocess.Popen([sys.executable, "-c", code], env=env())
    assert wait_for(pidfile.exists)
    child = int(pidfile.read_text())
    os.kill(p.pid, signal.SIGKILL)
    p.wait(timeout=5)
    assert alive(child) and held_now("t", ld)
    assert wait_for(lambda: not alive(child), timeout=10)
    assert wait_for(lambda: not held_now("t", ld), timeout=5)


# ------------------------------------------------------------------ exclusion (finding 18, O+S)

def test_stale_legacy_lock_race_lets_only_one_in(ld, tmp_path):
    """stale-race.log: two waiters both removed a stale lock and both entered. Waiter A is held
    for up to 2 s right after it sees the stale old-style lock; B must not get in meanwhile."""
    ld.mkdir(parents=True)
    (ld / "race.lock").mkdir()
    (ld / "race.lock" / "pid").write_text("999999\n")
    code = textwrap.dedent(f"""
        import os, sys, time
        from pathlib import Path
        from rvw.common import lock
        root, mode = Path({str(tmp_path)!r}), sys.argv[1]
        if mode == "A":
            real = lock._alive
            def stale(pid):
                ans = real(pid)
                if not ans:
                    (root / "a-observed-stale").touch()
                    t = time.monotonic() + 2
                    while not (root / "b-inside").exists() and time.monotonic() < t:
                        time.sleep(0.01)
                return ans
            lock._alive = stale
        with lock.held("race", poll_s=0.01, log=None):
            me, other = mode.lower(), "b" if mode == "A" else "a"
            (root / f"{{me}}-inside").touch()
            overlap = (root / f"{{other}}-inside").exists() and not (root / f"{{other}}-left").exists()
            print("overlap" if overlap else "alone", flush=True)
            time.sleep(0.3)
            (root / f"{{me}}-left").touch()
    """)
    a = subprocess.Popen([sys.executable, "-c", code, "A"], env=env(), stdout=subprocess.PIPE, text=True)
    assert wait_for((tmp_path / "a-observed-stale").exists)
    b = subprocess.Popen([sys.executable, "-c", code, "B"], env=env(), stdout=subprocess.PIPE, text=True)
    out_a, _ = a.communicate(timeout=20)
    out_b, _ = b.communicate(timeout=20)
    assert (out_a.strip(), out_b.strip()) == ("alone", "alone")


def test_many_concurrent_holders_never_overlap(ld, tmp_path):
    inside = tmp_path / "inside"
    code = textwrap.dedent(f"""
        import os, time
        from rvw.common.lock import held
        with held("c", poll_s=0.01, log=None):
            fd = os.open({str(inside)!r}, os.O_CREAT | os.O_EXCL)   # fails if another is inside
            time.sleep(0.05)
            os.close(fd); os.unlink({str(inside)!r})
    """)
    procs = [subprocess.Popen([sys.executable, "-c", code], env=env(), stderr=subprocess.PIPE, text=True)
             for _ in range(8)]
    errors = [p.communicate(timeout=60)[1] for p in procs]
    assert all(p.returncode == 0 for p in procs), errors


def test_threads_of_one_process_exclude_each_other(ld):
    inside, overlaps = [], []

    def body():
        with lock.held("th", poll_s=0.01, log=None):
            if inside:
                overlaps.append(1)
            inside.append(1)
            time.sleep(0.05)
            inside.pop()

    threads = [threading.Thread(target=body) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not overlaps


def test_spoofed_env_entry_does_not_bypass_the_lock(ld, tmp_path):
    flag = tmp_path / "ran"
    with lock.held("s", log=None):
        token = [t for t in os.environ["RVW_LOCKS_HELD"].split(",") if t.startswith("s:")][0]
        # A process that is not our descendant (double fork) and did not inherit the descriptor
        # carries a copy of the entry: it must still wait.
        subprocess.run(["bash", "-c", f"{WITH_LOCK} s touch {flag} </dev/null >/dev/null 2>&1 &"],
                       env=env(RVW_LOCKS_HELD=token), check=True)
        time.sleep(1.0)
        assert not flag.exists(), "a process with a copied RVW_LOCKS_HELD entry skipped the lock"
    assert wait_for(flag.exists)


def _stale_token(name, d, fd):
    st = os.stat(d / f"{name}.flock")
    return f"{name}:999999:{fd}:{st.st_dev}:{st.st_ino}"


def test_stale_entry_with_the_fresh_descriptor_number_does_not_bypass_a_free_lock(ld, monkeypatch):
    """Review 2 N2: a leaked RVW_LOCKS_HELD entry whose fd number equals the descriptor `held`
    opens for itself was taken as re-entry, so the lock was never taken (lock free)."""
    lock.status("f", ld)                     # creates f.flock
    probe = os.open(os.devnull, os.O_RDONLY)
    os.close(probe)                          # the next open gets this number
    monkeypatch.setenv("RVW_LOCKS_HELD", _stale_token("f", ld, probe))
    with lock.held("f", log=None):
        st = lock.status("f", ld)
        assert st["held"], "entered without taking the free lock"
        assert st["owner"]["pid"] == os.getpid()


def test_stale_entry_on_an_open_non_holding_descriptor_is_not_reentry(ld, monkeypatch):
    """A leaked entry naming a descriptor that is open on the lock file but holds nothing: with the
    lock free, `held` must take the lock itself (and record itself as owner)."""
    lock.status("g", ld)
    stray = os.open(ld / "g.flock", os.O_RDONLY)
    try:
        monkeypatch.setenv("RVW_LOCKS_HELD", _stale_token("g", ld, stray))
        with lock.held("g", log=None):
            st = lock.status("g", ld)
            assert st["held"] and st["owner"]["pid"] == os.getpid()
        assert not held_now("g", ld), "the stray descriptor kept the lock after the block"
    finally:
        os.close(stray)


# ------------------------------------------------------------------ re-entry (finding 2)

def test_shell_outer_python_inner(ld):
    code = "from rvw.common.lock import held\nwith held('z', log=None): print('inside')"
    r = subprocess.run([str(WITH_LOCK), "z", sys.executable, "-c", code], env=env(), capture_output=True,
                       text=True, timeout=30)
    assert r.returncode == 0 and r.stdout.strip() == "inside", r.stderr


def test_shell_outer_shell_inner_python_innermost(ld):
    code = "from rvw.common.lock import held\nwith held('z', log=None): print('inside')"
    r = subprocess.run([str(WITH_LOCK), "z", "bash", "-c", f"{WITH_LOCK} z {sys.executable} -c \"{code}\""],
                       env=env(), capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and r.stdout.strip() == "inside", r.stderr


def test_python_outer_shell_inner(ld):
    """Python used RVW_LOCK_HELD, the shell RVW_LOCKS_HELD: this direction deadlocked. (The child
    gets the descriptor through run_group; without it, it waits: review 4.)"""
    with lock.held("z", log=None):
        r = run_group([str(WITH_LOCK), "z", "echo", "inside"], capture=True, timeout=10)
    assert not r.timed_out and r.stdout.strip() == "inside", r.stderr


def test_python_outer_children_see_the_variable(ld):
    with lock.held("z", log=None):
        r = subprocess.run([sys.executable, "-c", "import os; print(os.environ.get('RVW_LOCKS_HELD', ''))"],
                           capture_output=True, text=True, timeout=10)
    assert r.stdout.strip().startswith(f"z:{os.getpid()}:")
    assert "RVW_LOCKS_HELD" not in os.environ


def test_environment_copied_before_the_lock_still_reenters(ld):
    """regress.Runner copies os.environ before it takes the lock; its children must not wait.
    run_group passes the descriptor with its RVW_LOCKS_HELD entry into the early copy."""
    early = env()
    with lock.held("z", log=None):
        r = run_group([str(WITH_LOCK), "z", "echo", "inside"], env=early, capture=True, timeout=10)
    assert not r.timed_out and r.stdout.strip() == "inside", r.stderr


def test_mcp_job_with_an_older_environment_still_reenters(ld):
    """Review 5: Job.run(env=...) with a snapshot taken under an outer lock overwrote the current
    RVW_LOCKS_HELD, so a child taking the inner lock waited on its own parent (deadlock). The
    merged environment carries the current entries, as run_group does. Bounded: no hang."""
    from rvw.mcp.jobs import Job
    job = Job("stale-env", "probe", {})
    child = "from rvw.common.lock import held\nwith held('inner', log=None): print('inside')"
    out = {}

    def work():   # the job's own thread takes the locks (review 10: locks are per thread)
        with lock.held("outer", log=None):
            before = dict(os.environ)
            with lock.held("inner", log=None):
                out["rc"] = job.run([sys.executable, "-c", child], env=before)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(20)
    blocked = t.is_alive()
    if blocked:
        job.request_cancel()
        t.join(Job.GRACE_S + 5)
    assert not blocked, "child blocked on a lock its parent holds"
    assert out.get("rc") == 0 and "inside" in job.tail(5)
    # Without a lock held, a stale entry in the given environment is not passed on.
    job2 = Job("no-lock", "probe", {})
    rc = job2.run([sys.executable, "-c", "import os; print('held=' + os.environ.get('RVW_LOCKS_HELD', ''))"],
                  env={"RVW_LOCKS_HELD": "inner:1:2:3"})
    assert rc == 0 and "held=" in job2.tail(5)


def test_nested_in_one_thread(ld):
    with lock.held("z", log=None):
        with lock.held("z", log=None):
            pass
        assert held_now("z", ld)
    assert not held_now("z", ld)


def test_unrelated_process_waits(ld, tmp_path):
    flag = tmp_path / "ran"
    with lock.held("z", log=None):
        # Detached (double fork): not our descendant, so it must wait for us.
        subprocess.run(["bash", "-c", f"{WITH_LOCK} z touch {flag} </dev/null >/dev/null 2>&1 &"], env=env(),
                       check=True)
        time.sleep(0.8)
        assert not flag.exists()
    assert wait_for(flag.exists)


# ------------------------------------------------------------------ queue and reporting (finding 3)

def test_waiters_are_served_in_arrival_order_and_see_the_holder(ld, tmp_path):
    order, release = tmp_path / "order", tmp_path / "release"
    hold = f"while [ ! -e {release} ]; do sleep 0.05; done"
    holder = subprocess.Popen([str(WITH_LOCK), "q", "bash", "-c", hold], env=env())
    assert wait_for(lambda: held_now("q", ld))
    waiters = []
    for i in range(4):
        waiters.append(subprocess.Popen([str(WITH_LOCK), "q", "bash", "-c", f"echo {i} >> {order}"], env=env(),
                                        stderr=subprocess.PIPE, text=True))
        assert wait_for(lambda: lock.status("q", ld)["waiting"] == i + 1), f"waiter {i} did not queue"
    release.touch()
    errs = [w.communicate(timeout=30)[1] for w in waiters]
    holder.wait(timeout=10)
    assert order.read_text().split() == ["0", "1", "2", "3"]
    assert f"held by pid {holder.pid}" in errs[0] and "bash -c while" in errs[0]
    assert "3 ahead in queue" in errs[3]


def test_dead_waiters_leave_the_queue(ld, tmp_path):
    holder = subprocess.Popen([str(WITH_LOCK), "d", "sleep", "1.5"], env=env())
    assert wait_for(lambda: held_now("d", ld))
    dead = subprocess.Popen([str(WITH_LOCK), "d", "true"], env=env())
    time.sleep(0.3)
    dead.kill()
    dead.wait()
    r = subprocess.run([str(WITH_LOCK), "d", "echo", "after"], env=env(), capture_output=True, text=True, timeout=15)
    assert r.stdout.strip() == "after"
    holder.wait(timeout=5)


# ------------------------------------------------------------------ old-style users (transition)

OLD_WITH_LOCK = r'''#!/usr/bin/env bash
set -euo pipefail
name="$1"; shift
case ",${RVW_LOCKS_HELD:-}," in *",$name,"*) exec "$@";; esac
dir="${RVW_LOCK_DIR:-$HOME/.cache/rvw-locks}"; mkdir -p "$dir"
lock="$dir/$name.lock"
until mkdir "$lock" 2>/dev/null; do
  pid="$(cat "$lock/pid" 2>/dev/null || true)"
  if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then rm -rf "$lock"; continue; fi
  sleep 0.1
done
echo $$ > "$lock/pid"
export RVW_LOCKS_HELD="${RVW_LOCKS_HELD:+$RVW_LOCKS_HELD,}$name"
trap 'rm -rf "$lock"' EXIT
"$@"
'''


def test_old_and_new_users_exclude_each_other(ld, tmp_path):
    old = tmp_path / "old-with-lock.sh"
    old.write_text(OLD_WITH_LOCK)
    old.chmod(0o755)
    flag = tmp_path / "flag"
    # An old-style holder blocks a new user.
    o = subprocess.Popen([str(old), "m", "sleep", "1.5"], env=env())
    assert wait_for(lambda: (ld / "m.lock" / "pid").exists())
    st = lock.status("m", ld)
    assert st["held"] and st["legacy_pid"] == o.pid
    n = subprocess.Popen([str(WITH_LOCK), "m", "touch", str(flag)], env=env(), stderr=subprocess.PIPE, text=True)
    time.sleep(0.8)
    assert not flag.exists()
    o.wait(timeout=10)
    _, err = n.communicate(timeout=10)
    assert flag.exists() and "old mkdir lock" in err
    # A new holder blocks an old-style user.
    flag.unlink()
    with lock.held("m", log=None):
        o = subprocess.Popen(["bash", "-c", f"{old} m touch {flag} </dev/null &"], env=env(),
                             start_new_session=True)
        time.sleep(0.8)
        assert not flag.exists()
    assert wait_for(flag.exists)
    o.wait(timeout=5)


def test_new_user_under_old_style_ancestor_does_not_wait(ld, tmp_path):
    old = tmp_path / "old-with-lock.sh"
    old.write_text(OLD_WITH_LOCK)
    old.chmod(0o755)
    r = subprocess.run([str(old), "m", str(WITH_LOCK), "m", "echo", "inside"], env=env(), capture_output=True,
                       text=True, timeout=15)
    assert r.stdout.strip() == "inside", r.stderr


def test_status_cli(ld):
    r = subprocess.run([sys.executable, "-m", "rvw.common.lock", "--status", "x"], capture_output=True, text=True,
                       timeout=10, env=env())
    assert '"held": false' in r.stdout
    bad = subprocess.run([str(WITH_LOCK), "a/b", "true"], capture_output=True, text=True, timeout=10, env=env())
    assert bad.returncode == 2 and "bad lock name" in bad.stderr


def test_held_fds_ignores_a_stale_entry_while_the_lock_is_free(ld, monkeypatch):
    """Like review 2 N2, for held_fds() (run_group calls it for every child): a leaked entry naming
    a descriptor open on the free lock file must not be reported, nor lock the file as a side effect."""
    lock.status("h", ld)
    stray = os.open(ld / "h.flock", os.O_RDONLY)
    try:
        monkeypatch.setenv("RVW_LOCKS_HELD", _stale_token("h", ld, stray))
        assert lock.held_fds() == []
        assert not held_now("h", ld)
    finally:
        os.close(stray)


# ------------------------------------------------------------------ review 4: re-entry needs the descriptor

def test_a_child_without_the_descriptor_waits_even_under_its_holding_parent(ld, tmp_path):
    """Review 4: a live ancestor alone let a child re-enter without the descriptor, so the child ran
    on after the parent released the lock, next to the next holder."""
    inside = tmp_path / "inside"
    code = f"from rvw.common.lock import held\nwith held('a', log=None): open({str(inside)!r}, 'w').write('1')"
    with lock.held("a", log=None):
        p = subprocess.Popen([sys.executable, "-c", code])     # no pass_fds: no descriptor
        time.sleep(1.5)
        assert not inside.exists(), "a child without the lock descriptor re-entered through its parent"
    assert p.wait(timeout=20) == 0 and inside.exists()


def test_run_group_child_re_enters_with_an_env_copied_before_the_lock(ld):
    """run_group passes the descriptors with their RVW_LOCKS_HELD entries, also into an env copied
    before the lock was taken (the case rule 3, 'held by an ancestor', used to cover)."""
    before = dict(os.environ)
    code = "from rvw.common.lock import held\nwith held('b', log=None): print('inside')"
    with lock.held("b", log=None):
        r = run_group([sys.executable, "-c", code], env=before, capture=True, timeout=20)
    assert not r.timed_out and r.stdout.strip() == "inside", r


def test_mcp_job_child_re_enters_the_lock_its_process_holds(ld):
    from rvw.mcp.jobs import Job
    job = Job("lock-child", "fixture", {})
    code = "from rvw.common.lock import held\nwith held('j', log=None): print('inside')"

    def work():   # the job's thread holds the lock, as an MCP handler does (review 10)
        with lock.held("j", log=None):
            job.run([sys.executable, "-c", code])

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(20)
    assert not t.is_alive(), "the job's child waited for the lock its own thread holds"
    assert "inside" in job.tail(10)


@pytest.mark.parametrize("starter", ["job", "run_group", "child_env"])
def test_a_child_of_another_thread_does_not_get_this_threads_lock(ld, tmp_path, starter):
    """Review 10: held_fds() returned every lock of the process, so Job.run (or run_group) in an
    unrelated thread passed another thread's lock to its child, which then entered the lock while
    the other thread still used it. Only the caller's own and inherited locks go to a child."""
    from rvw.mcp.jobs import Job
    entered = tmp_path / "entered"
    probe = [sys.executable, "-c", "import os; print('held=' + os.environ.get('RVW_LOCKS_HELD', ''))"]
    cmd = [sys.executable, "-m", "rvw.common.lock", "fixture", sys.executable, "-c",
           f"from pathlib import Path; Path({str(entered)!r}).write_text('x')"]
    taken, release = threading.Event(), threading.Event()

    def holder():
        with lock.held("fixture", log=None):
            taken.set()
            release.wait(30)

    h = threading.Thread(target=holder, daemon=True)
    h.start()
    assert taken.wait(10)
    try:
        if starter == "job":
            job = Job("other-thread", "probe", {})
            job.run(probe)
            assert "held=fixture" not in job.tail(5), job.tail(5)
            run = lambda: job.run(cmd)
        elif starter == "run_group":
            r = run_group(probe, capture=True, timeout=20)
            assert "fixture" not in r.stdout, r.stdout
            run = lambda: run_group(cmd, timeout=30)
        else:   # what the regress runner's adapter call uses
            e, fds = lock.child_env({"RVW_LOCKS_HELD": os.environ.get("RVW_LOCKS_HELD", "")})
            assert fds == [] and "RVW_LOCKS_HELD" not in e, (fds, e)
            assert os.environ.get("RVW_LOCKS_HELD", "").startswith("fixture:")
            run = lambda: run_group(cmd, timeout=30)
        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(1.5)
        assert not entered.exists(), "the child entered a lock another thread holds"
    finally:
        release.set()
        h.join(10)
    t.join(30)
    assert entered.exists()
