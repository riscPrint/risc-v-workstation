"""Exercise package tools through real registry dispatch, including worker subprocesses."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest

from rvw.common.lock import status as lock_status
from rvw.mcp.registry import Registry
from rvw.mcp.envelope import envelope
from rvw.results.generation import open_current
from race_injection import race_injector


@pytest.fixture
def registry():
    registry, problems = Registry.discover({"regress", "cosim", "cov", "perf"})
    assert not problems
    yield registry
    registry.jobs.shutdown()


def call(registry, name, **arguments):
    _, data, error = registry.call_json(name, arguments)
    assert not error, data
    if "job_id" in data:
        _, status, error = registry.call_json("job_status", {"job_id": data["job_id"], "wait_s": 60})
        assert not error and status["status"] == "done", status
        data = status["result"]
    return data


def test_regress_discovery_history_and_preview(registry, fake, rvw, tmp_path):
    core = str(fake.config)
    for options in ({}, {"suite": "isa"}):
        args = ["--suite", "isa"] if options else []
        assert call(registry, "regress_list", core=core, **options) == envelope(rvw("regress", "list", "--core", core, *args, "--json")[2])
    assert call(registry, "regress_history", core="fake", limit=2) == envelope(rvw("regress", "history", "--core", "fake", "--limit", 2, "--json")[2])
    out = str(tmp_path / "preview")
    actual = call(registry, "regress_run", core=core, suite="isa", out=out, dry_run=True, filter=["-p-"])
    expected = rvw("regress", "run", "--core", core, "--suite", "isa", "--out", out, "--dry-run", "--filter=-p-", "--json")[2]
    assert actual == expected
    assert not fake.calls("build")


def test_regress_run_compare_and_gate(registry, fake, rvw, tmp_path):
    core = str(fake.config)
    base, candidate = tmp_path / "base", tmp_path / "candidate"
    summary = call(registry, "regress_run", core=core, tier="quick", out=str(base))
    generation = open_current(base)
    assert summary == {**json.loads(generation.read_bytes("run.json")), "path": str(base),
                       "generation": generation.id}
    assert summary["generation"] == json.loads((base / "current").read_text())["id"]
    assert summary["ok"] and fake.calls("run-many")
    fake.commit({"rv64ui-p-add": "status=fail fail_code=7"}, msg="MCP core regression")
    result = call(registry, "regress_run", core=core, tier="quick", out=str(candidate), no_cache=True)
    assert not result["ok"]  # failing simulations still return the CLI JSON
    verdict = call(registry, "regress_compare", base=str(base), candidate=str(candidate), core=core)
    assert verdict["legacy_verdict"] == "reject" and verdict["new_failures"][0]["id"] == "rv64ui-p-add"
    assert verdict == envelope(rvw("regress", "compare", base, candidate, "--core", core, "--json")[2])
    gate = call(registry, "regress_gate", core=core, base=str(base), cand=str(candidate))
    assert gate == rvw("regress", "gate", "--core", core, "--base", base, "--cand", candidate, "--json")[2]
    history = call(registry, "regress_history", core="fake")
    assert len(history["runs"]) == 2


def test_regress_gate_runs_revisions(registry, fake):
    base = fake.commit(msg="mcp base")
    candidate = fake.commit({"rv64ui-p-add": "status=fail fail_code=9"}, msg="mcp candidate")
    verdict = call(registry, "regress_gate", core=str(fake.config), base_rev=base, cand_rev=candidate)
    assert verdict["verdict"] == "reject"
    assert verdict["gate"]["base"]["ran"] and verdict["gate"]["candidate"]["ran"]


def test_regress_known_tools(registry, fake, rvw):
    core = str(fake.config)
    added = call(registry, "regress_known_add", core=core, suite="isa", id="rv64ui-p-add",
                 signature="fail:7", reason="fixture failure", rev="abc")
    assert added["added"] == 1
    known = call(registry, "regress_known_list", core=core)
    assert known == envelope(rvw("regress", "known", "list", "--core", core, "--json")[2])
    assert known["known"][0] == added["entries"][0]
    removed = call(registry, "regress_known_remove", core=core, suite="isa", id="rv64ui-p-add")
    assert removed["removed"] == 1 and not call(registry, "regress_known_list", core=core)["known"]
    # add's timestamp is shared with the saved entry and the CLI's structured API.
    assert rvw("regress", "known", "add", "--core", core, "--suite", "isa", "--id", "x", "--signature", "fail:1",
               "--reason", "fixture", "--json")[2]["added"] == 1
    assert call(registry, "regress_known_list", core=core)["known"][0]["id"] == "x"


def wait_file(path):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(.05)
    pytest.fail(f"worker did not reach {path}")


def test_regress_cancel_kills_adapter_and_releases_lock(registry, fake, tmp_path):
    marker = tmp_path / "adapter.pid"
    wrapper = tmp_path / "adapter.py"
    adapter = Path(__file__).with_name("fake_adapter.py")
    wrapper.write_text(f"import os, pathlib, sys\n"
                       f"if sys.argv[1] == 'run-many': pathlib.Path({str(marker)!r}).write_text(str(os.getpid()))\n"
                       f"os.execv(sys.executable, [sys.executable, {str(adapter)!r}, *sys.argv[1:]])\n")
    fake.config.write_text(fake.config.read_text().replace(str(adapter), str(wrapper)))
    fake.prog("rv64ui-p-add", "sleep=30")
    _, started, error = registry.call_json("regress_run", {"core": str(fake.config), "suite": "isa", "filter": ["p-add$"]})
    assert not error
    wait_file(marker)
    pid = int(marker.read_text())
    _, cancelled, error = registry.call_json("job_cancel", {"job_id": started["job_id"]})
    assert not error and cancelled["status"] == "cancelled", cancelled
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert not lock_status("fake-test", tmp_path / "locks")["held"]
    assert not (tmp_path / "locks/fake-test.lock").exists()  # the old-style directory too


def test_perf_tools_match_cli(registry, tmp_path, rvw):
    path = tmp_path / "trace.log"
    path.write_text("Kanata\t0004\nC=\t0\nI\t0\t0\t0\nL\t0\t0\t80000000: addi a0,a0,1\n"
                    "S\t0\t0\tQ\nC\t2\nS\t0\t0\tIs\nC\t1\nR\t0\t0\t0\n")
    report = call(registry, "perf_report", path=str(path), window=2, isa="riscv", queue_stage="Q", issue_stage="Is")
    assert report == rvw("perf", path, "--window", 2, "--isa", "riscv", "--queue-stage", "Q", "--issue-stage", "Is", "--json")[2]
    assert report["summary"]["instret"] == 1
    saved = tmp_path / "report.json"
    saved.write_text(json.dumps(report))
    comparison = call(registry, "perf_compare", base=str(saved), candidate=str(saved), tolerance=.01)
    assert comparison == rvw("perf", "compare", saved, saved, "--tolerance", .01, "--json")[2]


def test_bad_arguments_and_failed_jobs(registry):
    _, result, error = registry.call_json("regress_run", {"core": "/missing.toml", "suite": "isa", "tier": "quick"})
    assert not error
    status = registry.call("job_status", {"job_id": result["job_id"], "wait_s": 60})
    assert status["status"] == "failed" and "exactly one" in status["error"]
    _, result, error = registry.call_json("regress_known_add", {"reason": "missing location"})
    assert error and "give --file or --core" in result["error"]
    _, result, error = registry.call_json("perf_report", {"path": "/missing.log"})
    status = registry.call("job_status", {"job_id": result["job_id"], "wait_s": 60})
    assert status["status"] == "failed" and "missing.log" in status["error"]


def test_long_and_readonly_annotations(registry):
    for name in ("regress_run", "regress_gate", "cosim_check", "cosim_generate",
                 "formal_bmc", "formal_xprop", "perf_report", "perf_compare"):
        spec = registry.tools[name]
        assert spec.long and spec.wants_job
    for name in ("regress_list", "regress_history", "regress_known_list", "cosim_check",
                 "formal_x_context", "perf_report", "perf_compare"):
        assert registry.tools[name].annotations["readOnlyHint"]


def test_tool_declarations_do_not_import_sdk():
    script = """
import sys
class BlockSDK:
    def find_spec(self, fullname, *args):
        if fullname == 'mcp' or fullname.startswith('mcp.'):
            raise AssertionError('MCP SDK imported by tool declaration')
sys.meta_path.insert(0, BlockSDK())
from rvw.mcp.registry import Registry
registry, problems = Registry.discover({'regress', 'cosim', 'formal', 'perf', 'wave', 'bundle', 'reduce', 'bisect'})
assert not problems, problems
# Structural check, not a fixed count: the count changes with every new tool.
packages = ('regress', 'cosim', 'formal', 'perf', 'wave', 'bundle', 'reduce', 'bisect')
for name, spec in registry.tools.items():
    assert spec.name == name and spec.description.strip(), name
    assert spec.input_schema.get('type') == 'object' and callable(spec.handler), name
assert {'job_status', 'job_cancel', 'job_list'} <= set(registry.tools)
for package in packages:
    assert any(name.startswith(package + '_') for name in registry.tools), package
registry.jobs.shutdown()
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)


def test_worker_cancel_unwinds_private_solver_group(tmp_path):
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.mcp.worker import run_function
    marker = tmp_path / "solver.pid"
    solver = tmp_path / "solver.py"
    solver.write_text(f"import os, pathlib, time\npathlib.Path({str(marker)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n")

    def solve(job):
        return run_function(job, "rvw.formal.common", "run",
                            {"cmd": [sys.executable, str(solver)], "cwd": str(tmp_path),
                             "log": str(tmp_path / "solver.log"), "timeout": 60})
    registry = Registry([ToolSpec("fixture_solve", "test solver cancellation", schema({}), solve, long=True)])
    try:
        _, started, error = registry.call_json("fixture_solve", {})
        assert not error
        wait_file(marker)
        pid = int(marker.read_text())
        _, status, error = registry.call_json("job_cancel", {"job_id": started["job_id"]})
        assert not error and status["status"] == "cancelled", status
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        registry.jobs.shutdown()


def test_cancel_during_process_spawn(monkeypatch):
    from rvw.mcp import jobs
    job = jobs.Job("spawn-race", "fixture", {})
    popen = jobs.subprocess.Popen

    def cancel_before_registration(*args, **kwargs):
        process = popen(*args, **kwargs)
        job.cancel()  # the process exists but is not in job._procs yet
        return process

    monkeypatch.setattr(jobs.subprocess, "Popen", cancel_before_registration)
    start = time.monotonic()
    with pytest.raises(jobs.Cancelled):
        job.run([sys.executable, "-c", "import time; time.sleep(10)"])
    assert time.monotonic() - start < 5


def test_job_run_stops_group_members_after_a_normal_leader_exit(tmp_path):
    """Review 4: after the leader exited normally, a background member of its group kept running."""
    from rvw.mcp import jobs
    job = jobs.Job("leader-exit", "fixture", {})
    marker = tmp_path / "member.pid"
    # the member closes the pipe so run() does not wait for it, and records its pid
    code = (f"import os, subprocess, sys; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
            f"stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); open({str(marker)!r}, 'w').write(str(p.pid))")
    assert job.run([sys.executable, "-c", code]) == 0
    pid = int(marker.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_regress_run_refuses_bad_seed_counts(registry, fake, tmp_path):
    """Review 11: a TOML `seeds = -1` made a successful MCP regress_run job with no tests."""
    core = str(fake.config)
    _, data, error = registry.call_json("regress_run", {"core": core, "suite": "isa", "seeds": -1,
                                                        "out": str(tmp_path / "a")})
    if not error and "job_id" in data:
        _, data, error = registry.call_json("job_status", {"job_id": data["job_id"], "wait_s": 60})
        error = error or data.get("status") != "done" or not data["result"].get("ok")
    assert error, data
    cfg = tmp_path / "neg.toml"
    cfg.write_text(fake.config.read_text().replace("seeds = 3", "seeds = -1"))
    _, data, error = registry.call_json("regress_run", {"core": str(cfg), "suite": "stress", "out": str(tmp_path / "b")})
    if not error and "job_id" in data:
        _, data, error = registry.call_json("job_status", {"job_id": data["job_id"], "wait_s": 60})
        error = error or data.get("status") != "done" or not data["result"].get("ok")
    assert error, data
    assert not (tmp_path / "b" / "run.json").exists()


@pytest.mark.parametrize("replace,revert", [(True, False), (False, True)])
def test_regress_compare_refuses_a_stale_root_c3_file(registry, fake, rvw, tmp_path, race_injector,
                                                   replace, revert):
    """Review 14: an old results.json beside a run set's run.json made regress_compare accept."""
    core = str(fake.config)
    base, candidate = tmp_path / "base", tmp_path / "candidate"
    call(registry, "regress_run", core=core, suite="isa", out=str(base))
    fake.commit({"rv64ui-p-add": "status=fail fail_code=7"}, msg="candidate fails with the same ELF")
    call(registry, "regress_run", core=core, suite="isa", out=str(candidate), no_cache=True)
    import rvw.results.schema as schema
    stale = candidate / "results.json"
    stale.write_text("unused workspace file")
    hook = race_injector.file(schema, "load_run_set", stale,
                              (base / "isa" / "small" / "results.json").read_bytes(),
                              occurrence=2, replace=replace, revert=revert)
    _, data, error = registry.call_json("regress_compare", {"base": str(base), "candidate": str(candidate), "core": core})
    assert hook.fired
    assert data.get("verdict") != "accept", data
    if error:
        cause = data["error"]
    else:
        assert data["verdict"] == "inconclusive", data
        cause = json.dumps({key: data.get(key) for key in ("cause", "reasons", "inconclusive")})
    assert "stale" in cause and str(stale) in cause, data
    code, _, _ = rvw("regress", "compare", base, candidate, "--core", core, "--json")
    assert code == 2 and "stale" in rvw.stderr and str(stale) in rvw.stderr
