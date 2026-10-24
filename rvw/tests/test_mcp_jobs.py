"""MCP job control and result handling (job regressions):
cancel stops SIGTERM-ignoring process trees, finished jobs are evicted, large results stay valid
JSON, the worker accepts plain module names, and wave tools run in a cancellable worker process."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time

import pytest

from rvw.mcp import jobs
from rvw.mcp.registry import Registry, discover
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return bool(r.stdout.strip()) and not r.stdout.strip().startswith("Z")


def wait_for(cond, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def plain_module(tmp_path, monkeypatch):
    """A top-level module (no dot in its name) importable here and by worker processes."""
    (tmp_path / "rvwplainmod.py").write_text(textwrap.dedent("""
        import os, signal, time
        def double(x):
            return {"value": 2 * x}
        def stubborn(pidfile, seconds=60):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            open(pidfile, "w").write(str(os.getpid()))
            time.sleep(seconds)
            return {"slept": seconds}
        def boom():
            raise ValueError("bad input")
    """))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(filter(None, [str(tmp_path), os.environ.get("PYTHONPATH")])))
    import importlib
    return importlib.import_module("rvwplainmod")


def test_cancel_kills_a_sigterm_ignoring_group(tmp_path, monkeypatch):
    """probe_cancel.log: a child that ignores SIGTERM stayed `running` after job_cancel."""
    monkeypatch.setattr(jobs.Job, "GRACE_S", 0.5)
    pidfile = tmp_path / "member.pid"
    code = (f"import os, signal, subprocess, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            f"m = subprocess.Popen([sys.executable, '-c', 'import signal, time; "
            f"signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(90)']); "
            f"open({str(pidfile)!r}, 'w').write(str(m.pid)); print('ready', flush=True); time.sleep(90)")

    def stubborn(job):
        return job.run([sys.executable, "-c", code])

    r = Registry([ToolSpec("t_stubborn", "fixture", schema({}), stubborn, long=True)])
    try:
        started = r.call("t_stubborn", {})
        assert wait_for(pidfile.exists)
        member = int(pidfile.read_text())
        t0 = time.monotonic()
        out = r.call("job_cancel", {"job_id": started["job_id"]})
        assert out["status"] == "cancelled", out
        assert time.monotonic() - t0 < 10
        assert wait_for(lambda: not alive(member), 5), "group member survived job_cancel"
    finally:
        r.jobs.shutdown(grace=0.2)


def test_in_process_handler_reports_cancelling(monkeypatch):
    monkeypatch.setattr(jobs.Job, "GRACE_S", 0.2)
    release = __import__("threading").Event()

    def busy(job):
        release.wait(10)
        return 1

    r = Registry([ToolSpec("t_busy", "fixture", schema({}), busy, long=True)])
    try:
        jid = r.call("t_busy", {})["job_id"]
        wait_for(lambda: r.jobs.get(jid).status == "running")
        out = r.call("job_cancel", {"job_id": jid})
        assert out["status"] == "cancelling"   # never reported as stopped before it is
        release.set()
        assert r.call("job_status", {"job_id": jid, "wait_s": 5})["status"] == "cancelled"
    finally:
        r.jobs.shutdown(grace=0.2)


def test_finished_jobs_are_evicted():
    m = jobs.JobManager(keep=3)
    r = Registry([ToolSpec("t_quick", "fixture", schema({"i": {"type": "integer"}}), lambda i: i, long=True)], jobs=m)
    ids = []
    for i in range(8):
        ids.append(r.call("t_quick", {"i": i})["job_id"])
        m.get(ids[-1]).done.wait(5)
        time.sleep(0.01)
    listed = r.call("job_list", {})["jobs"]
    assert len(listed) == 3 and [j["job_id"] for j in listed] == ids[-3:]
    _, err, is_error = r.call_json("job_status", {"job_id": ids[0]})
    assert is_error and "evicted" in err["error"]
    m.shutdown(grace=0.1)


def test_large_results_stay_valid_json():
    """registry cut text at 400,000 characters, mid-JSON."""
    big = {"rows": [{"i": i, "s": "x" * 50} for i in range(20000)], "summary": "kept", "blob": "y" * 300000}
    r = Registry([ToolSpec("t_big", "fixture", schema({}), lambda: big)])
    text, structured, is_error = r.call_json("t_big", {})
    assert not is_error and len(text) <= 400_000
    data = json.loads(text)
    assert data == structured and data["truncated"] is True and data["summary"] == "kept"
    assert 0 < len(data["rows"]) < 20000 and data["rows"][0] == big["rows"][0]
    paths = {c["path"] for c in data["truncation"]["cuts"]}
    assert "$.rows" in paths
    assert data["truncation"]["original_chars"] > 400_000
    # A list result keeps a valid shape too.
    r = Registry([ToolSpec("t_list", "fixture", schema({}), lambda: list(range(200000)))], max_text=50_000)
    text, structured, _ = r.call_json("t_list", {})
    assert len(text) <= 50_000 and json.loads(text)["truncated"] is True


@pytest.mark.parametrize("limit", [200, 1000, 3000, 3999, 5000])
def test_small_text_limits_are_kept(limit):
    """Review 2 N7: with max_text < 4000 the truncation record alone went over the limit."""
    from rvw.mcp.registry import fit
    big = {"rows": [{"i": i, "s": "x" * 50} for i in range(2000)], "names": {f"k{i}": i for i in range(20)},
           "blob": "y" * 30000}
    text, value = fit(big, limit)
    assert len(text) <= limit, (limit, len(text))
    assert json.loads(text) == value and value["truncated"] is True
    if limit >= 3000:   # a negative budget (limit - 4000) used to cut every value away
        assert value.get("rows"), value


def test_worker_accepts_a_module_name_without_a_dot(plain_module):
    """worker.py:26 raised IndexError for a module name without a dot."""
    r = Registry([ToolSpec("t_plain", "fixture", schema({"x": {"type": "integer"}}),
                           lambda x, job: run_function(job, "rvwplainmod", "double", {"x": x}), long=True)])
    jid = r.call("t_plain", {"x": 21})["job_id"]
    out = r.call("job_status", {"job_id": jid, "wait_s": 30})
    assert out["status"] == "done" and out["result"] == {"value": 42}, out
    r.jobs.shutdown(grace=0.1)


def test_isolated_tool_answers_inline_and_keeps_errors(plain_module):
    r = Registry([ToolSpec("t_double", "fixture", schema({"x": {"type": "integer"}}), plain_module.double,
                           isolate=True),
                  ToolSpec("t_boom", "fixture", schema({}), plain_module.boom, isolate=True)], sync_s=30)
    assert r.call("t_double", {"x": 4}) == {"value": 8}
    assert r.call("job_list", {})["jobs"] == []        # inline answers leave no job behind
    _, err, is_error = r.call_json("t_boom", {})
    assert is_error and err["error"] == "ValueError: bad input"
    _, err, is_error = r.call_json("t_double", {"y": 1})
    assert is_error and err["error"].startswith("bad arguments for t_double")
    r.jobs.shutdown(grace=0.1)


def test_slow_isolated_tool_becomes_a_cancellable_job(plain_module, tmp_path, monkeypatch):
    """wave_* parsed VCDs in the server process and could not be cancelled."""
    monkeypatch.setattr(jobs.Job, "GRACE_S", 0.5)
    pidfile = tmp_path / "worker.pid"
    r = Registry([ToolSpec("t_slow", "fixture", schema({"pidfile": {"type": "string"}}), plain_module.stubborn,
                           isolate=True)], sync_s=0.5)
    try:
        out = r.call("t_slow", {"pidfile": str(pidfile)})
        assert "job_id" in out and out["status"] == "running", out
        assert wait_for(pidfile.exists)
        pid = int(pidfile.read_text())
        assert r.call("job_cancel", {"job_id": out["job_id"]})["status"] == "cancelled"
        assert wait_for(lambda: not alive(pid), 5)
    finally:
        r.jobs.shutdown(grace=0.2)


VCD = """$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var wire 4 " cnt [3:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b0000 "
#5
1!
b0001 "
#10
0!
#15
1!
b0010 "
#20
0!
"""


def test_wave_tools_run_in_a_worker_process(tmp_path, monkeypatch):
    wave = tmp_path / "w.vcd"
    wave.write_text(VCD)
    tools, _ = discover({"wave"})
    r = Registry(tools, sync_s=60)
    calls = []
    real = run_function

    def spy(job, module, function, arguments, lock=None):
        calls.append((module, function))
        return real(job, module, function, arguments, lock)

    monkeypatch.setattr("rvw.mcp.registry.worker.run_function", spy)
    got = r.call("wave_changes", {"wave": str(wave), "regex": "cnt"})
    from rvw.wave import mcp_tools as wave_tools
    assert json.loads(json.dumps(got, default=list)) == json.loads(json.dumps(
        wave_tools._changes(str(wave), "cnt"), default=list))
    assert calls == [("rvw.wave.mcp_tools", "_changes")]
    r.jobs.shutdown(grace=0.1)


def test_cancel_during_worker_pipe_setup_stops_adapter(tmp_path, monkeypatch):
    """Review 15: job_cancel reported cancelled while the worker's separate group survived."""
    (tmp_path / 'pipe_setup_race.py').write_text(textwrap.dedent('''
        import time
        import sys
        from pathlib import Path
        from rvw.common import proc
        def run(pidfile):
            original = proc._Pipes
            class DelayedPipes(original):
                def __init__(self, process, input):
                    Path(pidfile).write_text(str(process.pid))
                    time.sleep(30)
                    super().__init__(process, input)
            proc._Pipes = DelayedPipes
            return proc.run_group([sys.executable, '-c', 'import time; time.sleep(120)']).returncode
    '''))
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(filter(None, [str(tmp_path), os.environ.get('PYTHONPATH')])))
    pidfile = tmp_path / 'adapter.pid'
    def run(job):
        return run_function(job, 'pipe_setup_race', 'run', {'pidfile': str(pidfile)})
    r = Registry([ToolSpec('setup_race', 'fixture', schema({}), run, long=True)])
    try:
        jid = r.call('setup_race', {})['job_id']
        assert wait_for(lambda: pidfile.exists() and pidfile.read_text())
        adapter = int(pidfile.read_text())
        result = r.call('job_cancel', {'job_id': jid})
        assert result['status'] == 'cancelled', result
        assert not alive(adapter), 'adapter survived a cancelled job'
        job = r.jobs.get(jid)
        assert job.done.is_set() and not job._procs
    finally:
        r.jobs.shutdown(grace=0.2)
        if pidfile.exists() and pidfile.read_text():
            try:
                os.killpg(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_job_output_pump_setup_error_stops_child(monkeypatch):
    children = []
    real_popen = jobs.subprocess.Popen
    def spawn(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child
    def fail_start(self):
        raise RuntimeError('output pump failed to start')
    monkeypatch.setattr(jobs.subprocess, 'Popen', spawn)
    monkeypatch.setattr(jobs.threading.Thread, 'start', fail_start)
    job = jobs.Job('setup', 'fixture', {})
    try:
        with pytest.raises(RuntimeError, match='output pump failed to start'):
            job.run([sys.executable, '-c', 'import time; time.sleep(60)'])
        assert children[0].poll() is not None and children[0].stdout.closed
        assert not job._procs
    finally:
        from rvw.common.proc import kill_group
        for child in children:
            kill_group(child, grace=0.1)


def test_cancel_waits_for_group_cleanup_after_leader_exit(monkeypatch):
    import threading
    cleanup_entered, release, cancelled = (threading.Event() for _ in range(3))
    original_signal = jobs.Job._signal
    def signal_group(process, sig):
        if sig == signal.SIGKILL:
            cleanup_entered.set()
            assert release.wait(10)
        original_signal(process, sig)
    monkeypatch.setattr(jobs.Job, '_signal', staticmethod(signal_group))
    r = Registry([ToolSpec('cleanup', 'fixture', schema({}),
                           lambda job: job.run([sys.executable, '-c', 'pass']), long=True)])
    waiter = None
    try:
        jid = r.call('cleanup', {})['job_id']
        assert cleanup_entered.wait(10)
        job = r.jobs.get(jid)
        def cancel():
            job.cancel()
            cancelled.set()
        waiter = threading.Thread(target=cancel)
        waiter.start()
        assert not cancelled.wait(0.1), 'cancel returned before group cleanup'
        assert job.state == 'cancelling'
        release.set()
        assert cancelled.wait(5) and job.done.wait(5)
        assert job.state == 'cancelled' and not job._procs
    finally:
        release.set()
        if waiter is not None:
            waiter.join(5)
        r.jobs.shutdown(grace=0.2)
