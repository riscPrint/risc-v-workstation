"""Regression tests for the review of 2026-10-21: stale MCP results,
script injection, vacuous passes, ignored --tie, solvers surviving a timeout, the port parser."""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.formal import common, flows

TOOLS = all(shutil.which(t) for t in ("yosys", "sby"))
needs_tools = pytest.mark.skipif(not TOOLS, reason="needs yosys and sby (source spinal-boom/env.sh)")

# q follows `a` one cycle later; the assertion fails as soon as a is 1 after the reset.
FAIL = """\
module t(
  input clk,
  input reset,
  input a,
  output reg q
);
  always @(posedge clk) begin if (reset) q <= 0; else q <= a; end
  always @(posedge clk) if (!reset) assert(!q);
endmodule
"""
NO_ASSERT = "module t(input clk, input reset, input a, output reg q);\n" \
            "  always @(posedge clk) if (reset) q <= 0; else q <= a;\nendmodule\n"
X_DUT = """\
module x_dut (
 input wire clk,
 input wire reset,
 output wire y
);
 reg unknown_reg;
 always @(posedge clk) unknown_reg <= ~unknown_reg;
 assign y = unknown_reg;
endmodule
"""
XTIE = """\
module xtie (
 input wire clk,
 input wire reset,
 input wire en,
 output wire y
);
 reg unknown_reg;
 always @(posedge clk) if(en) unknown_reg <= 1'b0;
 assign y=unknown_reg;
endmodule
"""
# Too hard for a few seconds of BMC: keeps the solver busy.
HARD = """\
module h(
  input clk,
  input reset,
  input [47:0] a,
  input [47:0] b,
  output reg [95:0] p
);
  always @(posedge clk) p <= a * b;
  always @(posedge clk) if (!reset) assert(!(p == 96'd4611685975477714963 && a > 1 && b > 1));
endmodule
"""


def _v(tmp_path, text, name="d.v"):
    f = tmp_path / name
    f.write_text(text)
    return f


def _result(out):
    return json.loads((Path(out) / "result.json").read_text())


def _rc(argv):
    try:
        return main(argv)
    except SystemExit as e:
        return e.code


# --------------------------------------------------------------------------------------------------
# Finding 6: module header parser


@needs_tools
def test_ports_several_per_line_and_per_declaration(tmp_path, probe_ports):
    f = _v(tmp_path, "// c\nmodule t(input clk, input reset, /* x */ input a, output reg q);\nendmodule\n"
                     "module u #(parameter W = 4) (\n  input wire [3:0] a, b,\n  output [7:0] y, z, input clk\n);\nendmodule\n")
    assert [(p.name, p.direction, p.width) for p in probe_ports([f], "t", tmp_path)] == [
        ("clk", "input", 1), ("reset", "input", 1), ("a", "input", 1), ("q", "output", 1)]
    assert [(p.name, p.direction, p.width) for p in probe_ports([f], "u", tmp_path)] == [
        ("a", "input", 4), ("b", "input", 4), ("y", "output", 8), ("z", "output", 8), ("clk", "input", 1)]


@needs_tools
def test_one_line_header_keeps_the_reset(tmp_path):
    # Before the fix the one-line header gave no ports: the reset was dropped and the wrapper left the
    # design's reset unconnected.
    f = _v(tmp_path, NO_ASSERT.replace("output reg q);", "output reg q);\n  always @(posedge clk) if (!reset) assert(!q);"))
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--depth", "4", "--out", str(tmp_path / "o")])
    r = _result(tmp_path / "o")
    assert r["reset"] == "reset" and ".reset(rvw_reset)" in (tmp_path / "o" / "rvw_formal_top.sv").read_text()
    assert rc == 1 and r["status"] == "fail"


def test_explicit_reset_must_exist(tmp_path):
    f = _v(tmp_path, FAIL)
    assert _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--reset", "rst", "--out", str(tmp_path / "o")]) == 2
    assert not (tmp_path / "o" / "result.json").exists()


# --------------------------------------------------------------------------------------------------
# Finding 2: names and paths cannot inject Yosys/sby script lines


@pytest.mark.parametrize("flow,extra", [
    ("xprop", ["--outputs", "--signal", "q\n!touch {pwned}"]),
    ("xprop", ["--outputs", "--clock", "clk\n!touch {pwned}"]),
    ("bmc", ["--engine", "smtbmc:yices\n\n[script]\n!touch {pwned}"]),
    ("bmc", ["--tie", "a\n!touch {pwned}=0"]),
    ("bmc", ["--top", "t\n!touch {pwned}"]),
    ("xprop", ["--outputs", "--signal", "q;!touch {pwned}"]),
    ("xprop", ["--outputs", "--signal", "q[0]*"]),
])
def test_script_injection_rejected(tmp_path, flow, extra):
    pwned = tmp_path / "PWNED"
    f = _v(tmp_path, FAIL)
    argv = ["formal", flow, "--verilog", str(f), "--top", "t", "--depth", "6", "--out", str(tmp_path / "o")]
    argv += [x.format(pwned=pwned) for x in extra]
    assert _rc(argv) == 2
    assert not pwned.exists()
    assert not (tmp_path / "o" / "result.json").exists()


def test_path_injection_rejected(tmp_path):
    pwned = tmp_path / "PWNED"
    f = _v(tmp_path, FAIL)
    out = tmp_path / f"o\n!touch {pwned}"
    assert _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--out", str(out)]) == 2
    assert not pwned.exists()


@needs_tools
def test_checks_report_names_are_validated(tmp_path):
    pwned = tmp_path / "PWNED"
    f = _v(tmp_path, FAIL)
    rep = tmp_path / "t.checks.json"
    rep.write_text(json.dumps({"checks": [], "channels": [
        {"kind": "stream", "path": "", "object": "s", "valid": f"q\n!touch {pwned}", "ready": None, "payload": []}]}))
    assert _rc(["formal", "xprop", "--verilog", str(f), "--top", "t", "--checks", str(rep), "--depth", "6",
                "--out", str(tmp_path / "o")]) == 2
    assert not pwned.exists()


@needs_tools
def test_bad_checks_report_names_require_regeneration(tmp_path, capsys):
    # Reports with empty path segments must be regenerated before a proof.
    f = _v(tmp_path, X_DUT)
    rep = tmp_path / "x.checks.json"
    rep.write_text(json.dumps({"checks": [], "channels": [
        {"kind": "flow", "path": "tile.frontend.", "object": "o", "valid": "tile.frontend..o_valid", "ready": None,
         "payload": []},
        {"kind": "flow", "path": "", "object": "y", "valid": "y", "ready": None, "payload": []}]}))
    rc = _rc(["formal", "xprop", "--verilog", str(f), "--top", "x_dut", "--checks", str(rep), "--depth", "6",
              "--out", str(tmp_path / "o")])
    assert rc == 2
    assert "regenerate the checks report" in capsys.readouterr().err
    assert not (tmp_path / "o" / "result.json").exists()
    # The same name given by the user is still a hard error.
    assert _rc(["formal", "xprop", "--verilog", str(f), "--top", "x_dut", "--signal", "tile.frontend..o_valid",
                "--depth", "6", "--out", str(tmp_path / "o2")]) == 2


@needs_tools
def test_unknown_signal_is_an_error(tmp_path):
    f = _v(tmp_path, X_DUT)
    assert _rc(["formal", "xprop", "--verilog", str(f), "--top", "x_dut", "--signal", "nope", "--depth", "6",
                "--out", str(tmp_path / "o")]) == 2


# --------------------------------------------------------------------------------------------------
# Finding 3: no pass without a checked assertion


@needs_tools
@pytest.mark.parametrize("free_reset,status", [(False, "pass"), (True, "fail")])
def test_bmc_can_reassert_a_free_reset(tmp_path, free_reset, status):
    f = _v(tmp_path, """module t(input clk, input reset);
reg armed=0;
always @(posedge clk) begin
  if (!reset) armed<=1;
  if (armed) assert(!reset);
end
endmodule
""")
    out = tmp_path / "out"
    extra = ["--free-reset"] if free_reset else []
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--depth", "6",
              "--out", str(out), *extra])
    assert rc == (0 if status == "pass" else 1)
    assert _result(out)["status"] == status


@needs_tools
def test_zero_assertions_is_no_checks(tmp_path):
    f = _v(tmp_path, NO_ASSERT)
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--depth", "4", "--out", str(tmp_path / "o")])
    r = _result(tmp_path / "o")
    assert rc == 1 and r["status"] == "no_checks" and r["assertions"] == 0


@needs_tools
def test_assertions_are_counted(tmp_path):
    f = _v(tmp_path, FAIL)
    _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--depth", "4", "--out", str(tmp_path / "o")])
    assert _result(tmp_path / "o")["assertions"] == 1


def test_count_asserts_follows_instances(tmp_path):
    il = tmp_path / "d.il"
    il.write_text("module \\sub\n  cell $assert $a1\n  end\n  cell $assert $a2\n  end\nend\n"
                  "module \\top\n  cell \\sub \\u0\n  end\n  cell \\sub \\u1\n  end\n  cell $assert $a3\n  end\nend\n")
    assert common.count_asserts(il, "top") == 5
    assert common.count_asserts(tmp_path / "missing.il", "top") is None


def test_reset_past_depth_is_rejected(tmp_path):
    f = _v(tmp_path, FAIL)
    for depth in (10, 11):
        assert _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--reset-cycles", "10", "--depth", str(depth),
                    "--out", str(tmp_path / f"o{depth}")]) == 2
        assert not (tmp_path / f"o{depth}" / "result.json").exists()


@needs_tools
def test_minimum_depth_checks_something(tmp_path):
    # The smallest accepted depth must find a failure possible in the first cycle after the reset.
    f = _v(tmp_path, FAIL.replace("assert(!q)", "assert(!a)"))
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "t", "--reset-cycles", "10", "--depth", "12",
              "--out", str(tmp_path / "o")])
    assert rc == 1 and _result(tmp_path / "o")["status"] == "fail"


@needs_tools
@pytest.mark.parametrize("reset_cycles,depth", [(2, 5), (255, 258)])
def test_xprop_arms_at_minimum_depth_and_large_reset(tmp_path, reset_cycles, depth):
    # Before the fix: depth 2 passed vacuously, and an 8-bit step counter saturating at 255 never armed
    # the checks with --reset-cycles 255.
    f = _v(tmp_path, X_DUT)
    rc = _rc(["formal", "xprop", "--verilog", str(f), "--top", "x_dut", "--outputs", "--reset-cycles", str(reset_cycles),
              "--depth", str(depth), "--out", str(tmp_path / "o")])
    r = _result(tmp_path / "o")
    assert rc == 1 and r["status"] == "fail" and [x["signal"] for x in r["x_reaches"]] == ["y"]
    assert r["assertions"] == 1


def test_xprop_too_shallow_is_rejected(tmp_path):
    f = _v(tmp_path, X_DUT)
    assert _rc(["formal", "xprop", "--verilog", str(f), "--top", "x_dut", "--outputs", "--reset-cycles", "2",
                "--depth", "4", "--out", str(tmp_path / "o")]) == 2


# --------------------------------------------------------------------------------------------------
# Finding 4: xprop honours --tie and records it


@needs_tools
def test_xprop_applies_ties(tmp_path):
    f = _v(tmp_path, XTIE)
    base = ["formal", "xprop", "--verilog", str(f), "--top", "xtie", "--outputs", "--depth", "6"]
    assert _rc(base + ["--out", str(tmp_path / "free")]) == 1
    assert _rc(base + ["--tie", "en=1", "--out", str(tmp_path / "tied")]) == 0
    r = _result(tmp_path / "tied")
    assert r["status"] == "pass" and r["ties"] == {"en": 1}
    assert "input en tied to 1" in r["restrictions"]


def test_tie_value_must_fit(tmp_path):
    f = _v(tmp_path, XTIE)
    for tie in ("en=2", "en=-1", "en=x", "en"):
        assert _rc(["formal", "xprop", "--verilog", str(f), "--top", "xtie", "--outputs", "--depth", "6",
                    "--tie", tie, "--out", str(tmp_path / "o")]) == 2


# --------------------------------------------------------------------------------------------------
# Finding 5: --timeout and SIGTERM stop the solvers


def _solvers_in(out: Path) -> list[int]:
    """Live processes whose working directory is under `out` (sby, its bash wrappers, solvers)."""
    ps = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout
    pids = [int(l.split(None, 1)[0]) for l in ps.splitlines()
            if any(k in l for k in ("yosys", "smtbmc", "yices", "sby", "bash -c"))]
    found = []
    for pid in pids:
        r = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True)
        cwd = [l[1:] for l in r.stdout.splitlines() if l.startswith("n")]
        if cwd and cwd[0].startswith(str(out.resolve())):
            found.append(pid)
    return found


def _wait_gone(out: Path, seconds: float = 20) -> list[int]:
    end = time.time() + seconds
    left = _solvers_in(out)
    while left and time.time() < end:
        time.sleep(0.5)
        left = _solvers_in(out)
    return left


@needs_tools
def test_timeout_stops_the_solvers(tmp_path):
    f = _v(tmp_path, HARD)
    out = tmp_path / "o"
    t0 = time.time()
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "h", "--depth", "30", "--timeout", "4", "--out", str(out)])
    assert rc == 1 and _result(out)["status"] == "timeout" and time.time() - t0 < 30
    left = _wait_gone(out, 5)
    for pid in left:
        os.kill(pid, signal.SIGKILL)
    assert not left, f"solver processes survived the timeout: {left}"


def test_tool_grace_is_below_the_mcp_job_grace(tmp_path, monkeypatch):
    # Round-2 finding: formal waited 10 s for sby after SIGTERM, but an MCP cancel SIGKILLs the CLI
    # after Job.GRACE_S, leaving sby's solver groups orphaned. Round 3: the grace must also leave sby time
    # to stop its solvers (3 s was too short under load), so it sits between 5 s and Job.GRACE_S - 2 s.
    from rvw.common.proc import Result
    from rvw.cov import proof
    from rvw.mcp.jobs import Job
    for grace in (common.TOOL_GRACE_S, proof.TOOL_GRACE_S):
        assert 5.0 <= grace <= Job.GRACE_S - 2.0
    seen = []

    def fake(argv, **kw):
        seen.append(kw.get("grace"))
        return Result(0, False, "x\n")
    monkeypatch.setattr(common, "run_group", fake)
    monkeypatch.setattr(proof, "run_group", fake)
    common.run(["true"], tmp_path, tmp_path / "log")
    # Version metadata now comes from the command capture, without subprocesses.
    with pytest.raises(RuntimeError, match='no command capture'):
        common.tool_versions()
    proof.run_job(["true"], tmp_path, tmp_path / "log2", 5)
    assert seen and all(g is not None and g < Job.GRACE_S for g in seen), seen


@needs_tools
def test_sigterm_stops_the_solvers(tmp_path):
    # An MCP cancel sends SIGTERM to the job's process group (the CLI); yosys/sby run in their own groups.
    f = _v(tmp_path, HARD)
    out = tmp_path / "o"
    p = subprocess.Popen([sys.executable, "-m", "rvw", "formal", "bmc", "--verilog", str(f), "--top", "h", "--depth", "30",
                          "--out", str(out)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end = time.time() + 60
        while time.time() < end and not list((out / "sby").glob("engine_0")):
            time.sleep(0.2)
        time.sleep(1.5)
        assert _solvers_in(out), "the solver never started"
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=30)
        left = _wait_gone(out, 15)
        for pid in left:
            os.kill(pid, signal.SIGKILL)
        assert not left, f"solver processes survived SIGTERM: {left}"
    finally:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)


# --------------------------------------------------------------------------------------------------
# Finding 1: the MCP tools never return a stale result


@needs_tools
def test_mcp_does_not_return_a_stale_result(tmp_path):
    from rvw.mcp.registry import Registry
    f = _v(tmp_path, FAIL)
    out = str(tmp_path / "o")
    registry, problems = Registry.discover({"formal"})
    assert not problems

    def call(args):
        _, started, error = registry.call_json("formal_bmc", args)
        assert not error, error
        _, status, error = registry.call_json("job_status", {"job_id": started["job_id"], "wait_s": 120})
        assert not error
        return status
    try:
        good = call({"verilog": [str(f)], "top": "t", "depth": 4, "out": out})
        assert good["status"] == "done" and good["result"]["status"] == "fail", good
        for bad in ({"verilog": [str(tmp_path / "missing.v")]}, {"top": "nope"}, {"depth": 1},
                    {"engine": "smtbmc:yices\n!true"}):
            st = call({"verilog": [str(f)], "top": "t", "depth": 4, "out": out, **bad})
            assert st["status"] != "done" and "result" not in st, (bad, st)
            assert not (tmp_path / "o" / "result.json").exists()
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize("code,payload,accepted", [
    (0, '{"status":"pass"}', True), (1, '{"status":"fail"}', True),
    (2, '{"status":"pass"}', False), (1, '{"status":"pass"}', False),
    (0, '{"status":"fail"}', False), (1, None, False), (1, '{', False), (0, '[]', False),
])
def test_mcp_runner_checks_exit_status_and_result(tmp_path, code, payload, accepted):
    from rvw.formal import mcp_tools
    from rvw.mcp.spec import ToolError
    out = tmp_path / "o"
    out.mkdir()

    class Job:
        def run(self, argv):
            if payload is not None:
                (out / "result.json").write_text(payload)
            return code

        def tail(self, n):
            return []
    run = mcp_tools._runner("bmc")
    if accepted:
        assert run(Job(), top="t", out=str(out)) == json.loads(payload)
    else:
        with pytest.raises(ToolError):
            run(Job(), top="t", out=str(out))


# --------------------------------------------------------------------------------------------------
# Round 10: a solver that did not run must never leave the previous run's PASS as this run's result

PASS_V = "module t(input clk, input reset, input a, output reg q);\n" \
         "  always @(posedge clk) q <= 1'b0;\n  always @(posedge clk) if (!reset) assert(!q);\nendmodule\n"


def _fake_sby(tmp_path, monkeypatch, code):
    """Put an `sby` on PATH that writes nothing and exits `code` (a failed or broken solver start)."""
    bin_dir = tmp_path / f"fakebin{code}"
    bin_dir.mkdir()
    sby = bin_dir / "sby"
    sby.write_text(f'#!/bin/sh\nif [ "$1" = --version ]; then echo fixture-sby; exit 0; fi\n'
                   f"echo simulated sby startup failure\nexit {code}\n")
    sby.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


@needs_tools
@pytest.mark.parametrize("code", [1, 0])
def test_failed_solver_start_does_not_reuse_the_old_model(tmp_path, monkeypatch, code):
    f = _v(tmp_path, PASS_V)
    out = tmp_path / "o"
    argv = ["formal", "bmc", "--verilog", str(f), "--top", "t", "--depth", "4", "--out", str(out)]
    assert _rc(argv) == 0 and _result(out)["status"] == "pass"
    assert (out / "sby" / "logfile.txt").is_file()
    _fake_sby(tmp_path, monkeypatch, code)
    assert _rc(argv) == 1
    r = _result(out)
    assert r["status"] == "error", r
    assert r["solver"] == {"exit": code, "log_rc": None}
    assert r["assertions"] is None and r["sby_log"] is None and r["failures"] == []
    assert not (out / "sby").exists()  # the old solver directory is gone, not reused


@needs_tools
def test_mcp_failed_solver_start_is_not_a_pass(tmp_path, monkeypatch):
    from rvw.mcp.registry import Registry
    f = _v(tmp_path, PASS_V)
    out = str(tmp_path / "o")
    registry, problems = Registry.discover({"formal"})
    assert not problems

    def call():
        _, started, error = registry.call_json("formal_bmc", {"verilog": [str(f)], "top": "t", "depth": 4, "out": out})
        assert not error, error
        _, status, error = registry.call_json("job_status", {"job_id": started["job_id"], "wait_s": 120})
        assert not error
        return status
    try:
        assert call()["result"]["status"] == "pass"
        _fake_sby(tmp_path, monkeypatch, 1)
        st = call()
        assert st.get("result", {}).get("status") != "pass", st
    finally:
        registry.jobs.shutdown()


def test_final_status_needs_this_runs_exit_zero():
    log = "SBY 1 [sby] DONE (PASS, rc=0)\n"
    assert common.final_status(0, log, 1) == "pass"
    assert common.final_status(1, log, 1) == "error"          # process failed, log says pass
    assert common.final_status(0, "", 1) == "error"
    assert common.final_status(2, "SBY 1 [sby] DONE (FAIL, rc=2)\n", 1) == "fail"
    assert common.final_status(0, "DONE (PASS, rc=0)\nDONE (FAIL, rc=2)\n", 1) == "error"
