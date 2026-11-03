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
        assert call(registry, "regress_list", core=core, **options) == rvw("regress", "list", "--core", core, *args, "--json")[2]
    assert call(registry, "regress_history", core="fake", limit=2) == rvw("regress", "history", "--core", "fake", "--limit", 2, "--json")[2]
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
    assert verdict["verdict"] == "reject" and verdict["new_failures"][0]["id"] == "rv64ui-p-add"
    assert verdict == rvw("regress", "compare", base, candidate, "--core", core, "--json")[2]
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
    assert known == rvw("regress", "known", "list", "--core", core, "--json")[2]
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


def dat(path, counts):
    path.write_text('# SystemC::Coverage-3\n' + ''.join(
        f"C '\x01f\x02logic.v\x01l\x02{n}\x01page\x02v_line/Unit\x01h\x02TOP.unit' {count}\n"
        for n, count in enumerate(counts, 1)))
    return path


def test_cov_merge_report_rank_select_and_functional(registry, tmp_path, rvw):
    a, b = dat(tmp_path / "a.dat", [1, 0]), dat(tmp_path / "b.dat", [0, 2])
    inputs = [f"A={a}", f"B={b}"]
    database = tmp_path / "coverage.json"
    data = call(registry, "cov_merge", inputs=inputs, source_root=str(tmp_path), out=str(database))
    assert data == rvw("cov", "merge", *inputs, "--source-root", tmp_path, "--json")[2]
    assert data == json.loads(database.read_text())
    report = call(registry, "cov_report", database=str(database))
    assert report == rvw("cov", "report", database, "--json")[2]
    assert report["summary"]["hit"] == 2
    ranking = call(registry, "cov_rank", database=str(database), exact=True)
    assert ranking == rvw("cov", "rank", database, "--exact", "--json")[2]
    assert ranking["selected"] == ["A", "B"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "Unit.scala"
    for value in (1, 2):
        source.write_text(f"val a={value}\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "Unit.scala"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=t@x",
                        "commit", "-qm", "fixture"], check=True)
    selected = call(registry, "cov_select", database=str(database), diff="HEAD~1..HEAD", repo=str(tmp_path))
    assert selected == rvw("cov", "select", database, "--diff", "HEAD~1..HEAD", "--repo", tmp_path, "--json")[2]
    assert selected["fallback_all"] and selected["tests"] == ["A", "B"]
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps({"schema": "rvw.rvfi/1", "xlen": 64, "isa": "rv64imc"}) + '\n' +
                     json.dumps({"order": 0, "insn": "0x00100093", "mode": 3, "rd": 1}) + '\n')
    functional = call(registry, "cov_functional", traces=[str(trace)])
    assert functional == rvw("cov", "functional", trace, "--json")[2]
    assert functional["retired"] == 1


@pytest.mark.parametrize('sim,eq,observed', [('FAIL', 'FAIL', 'killed'),
                                          ('PASS', 'PASS', 'equivalent'),
                                          ('PASS', 'FAIL', 'survived')])
def test_cov_mutation_report(registry, tmp_path, rvw, monkeypatch, sim, eq, observed):
    monkeypatch.setenv("RVW_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "database").mkdir()
    (tmp_path / "config.mcy").write_text("[options]\nsize 1\n")
    with sqlite3.connect(tmp_path / "database/db.sqlite3") as db:
        db.executescript('CREATE TABLE mutations(mutation_id INTEGER, mutation TEXT);'
                         'CREATE TABLE tags(mutation_id INTEGER, tag TEXT);'
                         'CREATE TABLE results(mutation_id INTEGER, test TEXT, result TEXT);'
                         'CREATE TABLE queue(mutation_id INTEGER, test TEXT, running INTEGER);'
                         'INSERT INTO mutations VALUES(0,"mutate -mode none");'
                         'INSERT INTO results VALUES(0,"sim","PASS");'
                         'INSERT INTO results VALUES(0,"eq","PASS");'
                         'INSERT INTO mutations VALUES(1,"mutate -mode inv");')
        db.executemany('INSERT INTO results VALUES(1,?,?)', [('sim', sim), ('eq', eq)])
    actual = call(registry, "cov_mutate", project=str(tmp_path), test=['sim'], equivalence_test=['eq'])
    rc, _, cli = rvw("cov", "mutate", tmp_path, "--test", "sim", "--equivalence-test", "eq", "--json")
    assert actual == cli
    assert rc == 3 and actual['status'] == 'inconclusive'
    assert actual['cause'] == 'input_not_captured:mcy_dependencies'
    assert all(actual['counts'][state] == 0 for state in ('killed', 'survived', 'equivalent', 'control'))
    assert actual['observed_counts'][observed] == 1
    assert actual['observed_counts']['control'] == 1 and not actual['control_failures']


@pytest.mark.skipif(not shutil.which("yosys"), reason="yosys not on PATH (source spinal-boom/env.sh)")
def test_cov_prove_job(registry, tmp_path, monkeypatch, rvw):
    # Synthetic solver status files test dispatch/provenance, not real proof evidence. The vacuity
    # guard elaborates the harness with the real Yosys.
    tools = tmp_path / "bin"
    tools.mkdir()
    for tool in ("sby", "z3"):
        path = tools / tool
        path.write_text(f"#!{sys.executable}\n" +
                        "import sys, shutil\nfrom pathlib import Path\n"
                        "if '-d' not in sys.argv: print('fixture-version'); sys.exit(0)\n"
                        "out = Path(sys.argv[sys.argv.index('-d') + 1])\n"
                        "out.mkdir()\n"
                        "src = out / 'src'; src.mkdir()\n"
                        "for source in Path(sys.argv[-1]).read_text().split('[files]\\n', 1)[1].splitlines():\n"
                        " if source.strip(): shutil.copyfile(source, src / Path(source).name)\n"
                        "sanity = 'sanity' in Path(sys.argv[-1]).name or 'cone' in Path(sys.argv[-1]).name\n"
                        "cover = 'mode cover' in Path(sys.argv[-1]).read_text() and not sanity\n"
                        "(out / 'status').write_text('FAIL' if cover else 'PASS')\n"
                        "sys.exit(2 if cover else 0)\n")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", str(tools) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("RVW_LOCK_DIR", str(tmp_path / "locks"))
    database, config, out = tmp_path / "coverage.json", tmp_path / "proof.json", tmp_path / "proof"
    (tmp_path / "logic.v").write_text("module fixture_logic; endmodule\n")
    data = call(registry, "cov_merge", inputs=[str(dat(tmp_path / "a.dat", [0]))],
                source_root=str(tmp_path), out=str(database))
    # The sanity state must be a real harness signal (an undeclared name is a free wire).
    (tmp_path / "harness.sv").write_text("module fixture(input clk);\nreg state = 0;\n"
                                         "always @(posedge clk) begin state <= !state;\n// RVW_POINT\nend\nendmodule\n")
    config.write_text(json.dumps({"sources": ["logic.v"], "harness": "harness.sv", "top": "fixture",
                                  "sanity_state": ["state"], "reset": None,  # no reset: stated, not guessed
                                  "points": [{"point_id": data["points"][0]["id"],
                                              "expression": "state && 1'b0", "reason": "synthetic fixture"}]}))
    result = call(registry, "cov_prove", database=str(database), config=str(config), work_dir=str(out))
    assert result == json.loads((out / "exclusions.json").read_text())
    assert result["point_universe"] == data["point_universe"]
    point = result["points"][0]
    assert point["unreachable"] and point["jobs"]["cover"]["status"] == "FAIL"
    assert point["jobs"]["prove"]["status"] == "PASS" and point["cone"]["signals"] == ["state"]
    assert result["sanity"]["passed"] and result["sanity"]["expression"] == "!$initstate && !$stable({state})"
    shutil.rmtree(out)
    assert result == rvw("cov", "prove", database, "--config", config, "--work-dir", out, "--json")[2]
    expected = {"sby", "yosys", "z3", "yosys-smtbmc", "yosys-witness", "bash", "yices-smt2"}
    # OSS CAD Suite uses a tabbypy3 launcher. Homebrew ships Python directly.
    uses_tabby = "tabbypy3" in Path(shutil.which("yosys-smtbmc")).read_text()
    if uses_tabby:
        expected.add("tabbypy3")
    assert set(result["tools"]) == expected
    assert set(result["tool_bindings"]) == set(result["tools"])
    for name, binding in result["tool_bindings"].items():
        assert result["tools"][name]["executable"] == binding["input"]["resolved"]
        assert result["tools"][name]["sha256"] == binding["input"]["sha256"]
    # The release launcher runs the bound shell and Python, including solver probes.
    smtbmc = Path(result["tool_bindings"]["yosys-smtbmc"]["command"]["path"]).read_text()
    if uses_tabby:
        assert result["tools"]["bash"]["executable"] in smtbmc
        assert result["tool_bindings"]["tabbypy3"]["command"]["path"] in smtbmc
    else:
        assert "tabbypy3" not in smtbmc
        assert result["tools"]["yosys-smtbmc"]["executable"] in smtbmc
    assert not lock_status("boom", tmp_path / "locks")["held"]


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
    for name in ("regress_run", "regress_gate", "cosim_check", "cosim_generate", "cov_merge", "cov_report",
                 "cov_rank", "cov_select", "cov_functional", "cov_prove", "cov_mutate", "perf_report", "perf_compare"):
        spec = registry.tools[name]
        assert spec.long and spec.wants_job
    for name in ("regress_list", "regress_history", "regress_known_list", "cosim_check",
                 "cov_report", "cov_rank", "cov_select", "cov_functional", "perf_report", "perf_compare"):
        assert registry.tools[name].annotations["readOnlyHint"]


def test_cov_error_json_and_readonly_arguments(registry, rvw, tmp_path):
    missing = str(tmp_path / "missing.json")
    # A missing capture exits 3 with an inconclusive cause; MCP fails the job (C7).
    code, _, printed = rvw("cov", "report", missing, "--json")
    assert code == 3 and printed["schema"] == "rvw.coverage-error/1"
    assert printed["status"] == "inconclusive" and printed["cause"].startswith("input_not_captured:")
    for tool, args in (("cov_report", {"database": missing}), ("cov_rank", {"database": missing}),
                       ("cov_select", {"database": missing, "diff": "A..B"}),
                       ("cov_functional", {"traces": [missing]})):
        _, started, error = registry.call_json(tool, args)
        assert not error
        status = registry.call("job_status", {"job_id": started["job_id"], "wait_s": 60})
        assert status["status"] == "failed" and "missing.json" in status["error"], (tool, status)
    # Read-only tools reject write options even through Registry without SDK schema checks.
    _, result, error = registry.call_json("cov_report", {"database": missing, "out": str(tmp_path / "bad.json")})
    assert error and "out" in result["error"] and "job_id" not in result
    assert not (tmp_path / "bad.json").exists()


def test_tool_declarations_do_not_import_sdk():
    script = """
import sys
class BlockSDK:
    def find_spec(self, fullname, *args):
        if fullname == 'mcp' or fullname.startswith('mcp.'):
            raise AssertionError('MCP SDK imported by tool declaration')
sys.meta_path.insert(0, BlockSDK())
from rvw.mcp.registry import Registry
registry, problems = Registry.discover({'regress', 'cosim', 'cov', 'perf', 'wave', 'bundle', 'reduce', 'bisect'})
assert not problems, problems
assert len(registry.tools) == 32  # twenty-eight package tools plus four job tools
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
        return run_function(job, "rvw.cov.proof", "run_job",
                            {"argv": [sys.executable, str(solver)], "cwd": str(tmp_path),
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
