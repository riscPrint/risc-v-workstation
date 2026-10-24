"""rvw.runs: fresh attempt directories, process-tree timeouts, replay path mapping, C1 loading."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

import rvw.runs as runs
from rvw.runs import adapter

FAKE = str(Path(__file__).parent / "fake_debug_adapter.py")
SYMS_ELF = str(Path(__file__).parent / "data" / "reduce_symbols.elf")


@pytest.fixture(autouse=True)
def nolock(monkeypatch):
    monkeypatch.setenv("RVW_NO_LOCK", "1")
    monkeypatch.setenv("RVW_NO_RUN_MANY", "1")
    monkeypatch.delenv("FAKE_CORE", raising=False)


def test_failed_rerun_never_returns_an_older_result(tmp_path):
    # Review finding (S, /tmp/review-debug-sol/probes.log): the second, failing invocation returned
    # the first invocation's result.json from the same --out directory.
    cmd = adapter.Command(exe=[sys.executable, FAKE], opts={"--elf": SYMS_ELF, "--seed": "9"})
    first = adapter.execute(cmd, tmp_path / "out")
    assert first.run is not None and first.run.get("status") == "assert"
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "build-broken").touch()
    cmd.env["FAKE_CORE"] = str(broken)
    second = adapter.execute(cmd, tmp_path / "out")
    assert second.run is None and "no result.json" in second.error
    assert second.dir != first.dir and second.returncode != 0
    assert "build failed" in second.log.read_text()


def test_attempt_never_writes_into_an_existing_dir_or_link(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (tmp_path / "link").symlink_to(other)
    d = adapter.fresh_dir(tmp_path / "link")
    assert d.name == "link-2" and not any(other.iterdir())


def test_timeout_stops_the_whole_process_tree(tmp_path):
    # Review finding (O+S): subprocess.run(timeout=) killed only the direct child (the lock
    # wrapper); the simulator below it kept running.
    pidf = tmp_path / "grandchild.pid"
    script = tmp_path / "adapter.py"
    script.write_text(
        "import subprocess, sys, time, pathlib\n"
        "p = subprocess.Popen(['sleep', '60'])\n"
        f"pathlib.Path({str(pidf)!r}).write_text(str(p.pid))\n"
        "time.sleep(60)\n")
    cmd = adapter.Command(exe=[sys.executable, str(script)], opts={"--elf": "x"})
    t = time.monotonic()
    at = adapter.execute(cmd, tmp_path / "out", timeout=2)
    assert at.timed_out and at.run is None and time.monotonic() - t < 30
    pid = int(pidf.read_text())
    time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_timed_out_attempt_does_not_return_a_result(tmp_path):
    script = tmp_path / "adapter.py"
    script.write_text(
        "import json, sys, time, os\n"
        "out = sys.argv[sys.argv.index('--out') + 1]\n"
        "json.dump({'schema': 'rvw.run/1', 'status': 'pass'}, open(os.path.join(out, 'result.json'), 'w'))\n"
        "time.sleep(60)\n")
    at = adapter.execute(adapter.Command(exe=[sys.executable, str(script)]), tmp_path / "o", timeout=1)
    assert at.timed_out and at.run is None


def test_replay_paths_resolve_against_the_current_checkout(tmp_path, capsys):
    root = tmp_path / "tools"
    (root / "RiscvSim" / "boom").mkdir(parents=True)
    (root / "RiscvSim" / "boom" / "run.sh").write_text("#!/bin/sh\n")
    here = str((root / "RiscvSim" / "boom" / "run.sh").resolve())
    # Repo-relative (what C1 asks adapters to write): resolved here, no warning.
    c = adapter.parse_replay("RiscvSim/boom/run.sh run --elf a --out d", root)
    assert c.exe == [here] and not c.notes
    # Absolute, from another worktree (old adapters): mapped here, with a warning.
    c = adapter.parse_replay("/work/rvw-bundle/RiscvSim/boom/run.sh run --elf a --out d", root)
    assert c.exe == [here] and c.notes and "rvw-bundle" in capsys.readouterr().err
    # Absolute and already this checkout: no warning.
    c = adapter.parse_replay(f"{here} run --elf a", root)
    assert c.exe == [here] and not c.notes
    # Other absolute adapters (an interpreter, a test adapter) are kept.
    c = adapter.parse_replay(f"{sys.executable} /opt/x/adapter.py run --elf a", root)
    assert c.exe == [sys.executable, "/opt/x/adapter.py"]


def test_runs_uses_the_canonical_c1_loader(tmp_path):
    assert not hasattr(runs, "load_run")
    d = tmp_path / "r"
    d.mkdir()
    (d / "result.json").write_text(json.dumps({"schema": "rvw.run/1", "status": "assert", "cycles": 5,
                                               "message": "x (lsu.scala:1241)", "details": {"k": 1}}))
    r = runs.open_run(d)
    assert r.dir == d.resolve() and r.result.status == "assert" and r.get("details") == {"k": 1}
    assert runs.signature(r.data) == "assert:lsu.scala:1241"
    (d / "result.json").write_text(json.dumps({"schema": "rvw.run/1", "status": "weird"}))
    with pytest.raises(ValueError):
        runs.open_run(d)
    with pytest.raises(FileNotFoundError):
        runs.open_run(tmp_path / "missing")


# --- round 2: the per-trial timeout starts after the core lock is held -----------------------

def _hold_lock(tmp_path, name, seconds):
    """Another process holds lock `name` for `seconds`; returns once it holds it."""
    import subprocess
    from rvw.common import lock
    p = subprocess.Popen([sys.executable, "-m", "rvw.common.lock", name, "sleep", str(seconds)])
    deadline = time.monotonic() + 20
    while not lock.status(name)["held"]:
        assert time.monotonic() < deadline and p.poll() is None
        time.sleep(0.05)
    return p


@pytest.mark.parametrize("many", [False, True])
def test_timeout_does_not_count_the_lock_wait(tmp_path, monkeypatch, many):
    # Review 2: the adapter ran under with-lock.sh inside the timeout, so a trial queued behind
    # another job's lock timed out (wall-timeout / no reproduction) without ever running.
    monkeypatch.delenv("RVW_NO_LOCK")
    monkeypatch.delenv("RVW_LOCKS_HELD", raising=False)
    monkeypatch.setenv("RVW_LOCK_DIR", str(tmp_path / "locks"))
    if many:
        monkeypatch.delenv("RVW_NO_RUN_MANY")
    holder = _hold_lock(tmp_path, "fakecore", 4)
    try:
        cmd = adapter.Command(exe=[sys.executable, FAKE], opts={"--elf": SYMS_ELF, "--seed": "9"})
        cmds = [cmd, cmd.set(seed=1)] if many else [cmd]
        ats = adapter.execute_many(cmds, [tmp_path / f"o{i}" for i in range(len(cmds))], core="fakecore",
                                   timeout=2)
    finally:
        holder.wait()
    for at in ats:
        assert not at.timed_out and at.run is not None, (at.error, at.log.read_text())
        assert at.lock_wait > 1.5 and at.wall < 2
    assert "waited" in ats[0].log.read_text()


def test_adapter_that_takes_the_lock_again_runs_at_once(tmp_path, monkeypatch):
    # The adapter (RiscvSim/boom/run.sh) wraps its build in with-lock.sh <core>: under rvw's lock it
    # must not queue behind itself. It re-enters through the descriptor rvw passes (review 4: being
    # a child of the holder is not enough), so a Python adapter keeps it for its children
    # (close_fds=False), as bash does.
    monkeypatch.delenv("RVW_NO_LOCK")
    monkeypatch.delenv("RVW_LOCKS_HELD", raising=False)
    monkeypatch.setenv("RVW_LOCK_DIR", str(tmp_path / "locks"))
    wl = Path(__file__).resolve().parents[2] / "scripts" / "with-lock.sh"
    script = tmp_path / "adapter.py"
    script.write_text(
        "import json, os, subprocess, sys\n"
        f"subprocess.run([{str(wl)!r}, 'fakecore', 'true'], check=True, close_fds=False)\n"
        "out = sys.argv[sys.argv.index('--out') + 1]\n"
        "json.dump({'schema': 'rvw.run/1', 'status': 'pass', 'core': 'fakecore'}, "
        "open(os.path.join(out, 'result.json'), 'w'))\n")
    at = adapter.execute(adapter.Command(exe=[sys.executable, str(script)]), tmp_path / "o",
                         core="fakecore", timeout=20)
    assert not at.timed_out and at.run is not None, at.log.read_text()
    assert at.wall < 15


def test_captured_run_parses_once_with_original_directory(tmp_path, monkeypatch):
    from rvw.common.capture import Capture
    from rvw.runs import result

    path = tmp_path / "run"
    path.mkdir()
    (path / "result.json").write_text(json.dumps({"schema": "rvw.run/1", "status": "pass"}))
    capture = Capture(tmp_path / "capture")
    monkeypatch.setattr(result, "load_result", lambda *a: pytest.fail("recaptured C1 result"))
    run = result.open_run(path, capture=capture)
    assert run.dir == run.result.path == path.resolve()
    assert len(capture.record()["files"]) == 1


def test_captured_run_refuses_nonregular_descriptor(tmp_path, monkeypatch):
    from rvw.common.capture import Capture
    from rvw.runs import result

    path = tmp_path / "result.json"
    path.write_text('{"schema":"rvw.run/1","status":"pass"}')
    capture = Capture(tmp_path / "capture")
    item = capture.file(path)
    item.copy.unlink()
    os.mkfifo(item.copy)
    with pytest.raises(ValueError, match="not a regular file"):
        result.open_run(path, capture=capture)
