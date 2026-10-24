"""Round-14 review findings for `rvw formal`: designs with more than one clock (false pass with
`multiclock off`), and a note on stdout that made `--json` output invalid."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.formal import common

TOOLS = all(shutil.which(t) for t in ("yosys", "sby"))
needs_tools = pytest.mark.skipif(not TOOLS, reason="needs yosys and sby (source spinal-boom/env.sh)")
needs_verilator = pytest.mark.skipif(not (TOOLS and shutil.which("verilator")), reason="needs verilator")

# /tmp/review14-c/multiclock/top.sv: two independent clocks. With `multiclock off` both registers step
# together and the assertion holds; with independent clocks it fails at the second edge of clk.
DUAL = """\
module DualClock(input clk, input other_clk);
  reg a = 0;
  reg b = 0;
  always @(posedge clk) a <= !a;
  always @(posedge other_clk) b <= !b;
  always @(posedge clk) assert (a == b);
endmodule
"""
# A clock made by logic from --clock (a gated clock): it does not tick on every edge of clk.
GATED = """\
module gated(input clk, input reset, input en, output reg q);
  reg a = 0;
  wire gclk = clk & en;
  always @(posedge clk) a <= !a;
  always @(posedge gclk) q <= a;
  always @(posedge clk) if (!reset) assert (q == 0 || q == 1);
endmodule
"""
# Registers on both edges of --clock: one step per cycle cannot model the half-cycle path.
NEGEDGE = """\
module both(input clk, input reset, input d, output reg q);
  reg a;
  always @(posedge clk) a <= d;
  always @(negedge clk) q <= a;
  always @(posedge clk) if (!reset) assert (q == a || q != a);
endmodule
"""
# A register that only the second clock writes, read by an output: if other_clk never ticks it stays X.
XDUAL = """\
module xdual(input clk, input other_clk, input reset, output y);
  reg r;
  always @(posedge other_clk) r <= 1'b0;
  assign y = r;
endmodule
"""
# One clock, a synchronous reset, a memory with a synchronous write and an asynchronous read, and a
# clocked assertion: accepted.
ONE = """\
module one(input clk, input reset, input [1:0] wa, input [1:0] ra, input [3:0] wd, output [3:0] rd);
  reg [3:0] mem [0:3];
  reg [3:0] cnt;
  always @(posedge clk) if (reset) cnt <= 0; else cnt <= cnt + 1;
  always @(posedge clk) mem[wa] <= wd;
  assign rd = mem[ra];
  always @(posedge clk) if (!reset) assert (cnt < 16);
endmodule
"""
NO_RESET = "module SingleClock(input clk, input bad);\n  always @(posedge clk) assert(!bad);\nendmodule\n"


def _v(tmp_path, text, name="d.sv"):
    f = tmp_path / name
    f.write_text(text)
    return f


def _rc(argv):
    try:
        return main(argv)
    except SystemExit as e:
        return e.code


# --------------------------------------------------------------------------------------------------
# Finding 1: more than one clock


@needs_tools
def test_bmc_refuses_two_independent_clocks(tmp_path, capsys):
    f = _v(tmp_path, DUAL)
    out = tmp_path / "bmc"
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "DualClock", "--depth", "8", "--out", str(out), "--json"])
    err = capsys.readouterr().err
    assert rc == 2, "two independent clocks must not be proven as one"
    assert not (out / "result.json").exists()
    assert "other_clk" in err and "multiclock off" in err


@needs_tools
def test_bmc_refuses_a_gated_clock(tmp_path, capsys):
    f = _v(tmp_path, GATED)
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "gated", "--depth", "4", "--out", str(tmp_path / "o")])
    assert rc == 2 and not (tmp_path / "o" / "result.json").exists()
    assert "CLK is gclk, not clk" in capsys.readouterr().err


@needs_tools
def test_bmc_refuses_the_falling_edge(tmp_path, capsys):
    f = _v(tmp_path, NEGEDGE)
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "both", "--depth", "4", "--out", str(tmp_path / "o")])
    assert rc == 2 and not (tmp_path / "o" / "result.json").exists()
    assert "falling edge of clk" in capsys.readouterr().err


@needs_tools
def test_xprop_refuses_two_clocks(tmp_path, capsys):
    # With multiclock off, r is written at the first step and y is never X; with independent clocks
    # other_clk may never tick and y stays X.
    f = _v(tmp_path, XDUAL)
    rc = _rc(["formal", "xprop", "--verilog", str(f), "--top", "xdual", "--outputs", "--depth", "6",
              "--out", str(tmp_path / "x")])
    assert rc == 2 and not (tmp_path / "x" / "result.json").exists()
    assert "other_clk" in capsys.readouterr().err


@needs_verilator
def test_from_sim_refuses_two_clocks(tmp_path, capsys):
    f = _v(tmp_path, DUAL)
    (tmp_path / "tb.sv").write_text(
        "module tb; reg clk = 0, other_clk = 0; DualClock dut(.clk(clk), .other_clk(other_clk));\n"
        "always #5 clk = ~clk; always #7 other_clk = ~other_clk;\n"
        "initial begin $dumpfile(\"t.vcd\"); $dumpvars(0, tb); #200 $finish; end endmodule\n")
    # the simulation itself breaks the assertion (the clocks are independent): build it without assertions
    subprocess.run(["verilator", "--binary", "--trace", "--timing", "--no-assert", "-Wno-fatal", "tb.sv", "d.sv",
                    "--top", "tb",
                    "-o", "sim"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["./obj_dir/sim"], cwd=tmp_path, check=True, capture_output=True)
    out = tmp_path / "fs"
    rc = _rc(["formal", "from-sim", "--verilog", str(f), "--top", "DualClock", "--trace", str(tmp_path / "t.vcd"),
              "--scope", "tb.dut", "--cycle", "2", "--depth", "6", "--out", str(out)])
    assert rc == 2 and not (out / "result.json").exists()
    assert "other_clk" in capsys.readouterr().err


@needs_tools
def test_one_clock_with_sync_reset_and_memory_is_accepted(tmp_path):
    f = _v(tmp_path, ONE)
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "one", "--depth", "5", "--out", str(tmp_path / "o")])
    r = json.loads((tmp_path / "o" / "result.json").read_text())
    assert rc == 0 and r["status"] == "pass" and r["assertions"] == 1
    assert common.clock_problems(tmp_path / "o" / common.CLOCKS_JSON, "one", "clk") == []


def _probe(tmp_path, cells, ports=None):
    p = tmp_path / "probe.json"
    p.write_text(json.dumps({"modules": {"m": {
        "ports": ports or {"clk": {"direction": "input", "bits": [2]}, "c2": {"direction": "input", "bits": [3]}},
        "netnames": {"clk": {"bits": [2]}, "c2": {"bits": [3]}}, "cells": cells}}}))
    return p


def test_clock_problems_reads_memory_ports_and_triggers(tmp_path):
    ok = {
        "ff": {"type": "$dff", "parameters": {"CLK_POLARITY": "1"}, "connections": {"CLK": [2]}},
        # two write ports on clk; one asynchronous read port (its clock is x and not enabled)
        "mem": {"type": "$mem_v2", "parameters": {"RD_CLK_ENABLE": "0", "RD_CLK_POLARITY": "0",
                                                  "WR_CLK_ENABLE": "11", "WR_CLK_POLARITY": "11"},
                "connections": {"RD_CLK": ["x"], "WR_CLK": [2, 2]}},
        "chk": {"type": "$check", "parameters": {"TRG_ENABLE": "0" * 31 + "1", "TRG_POLARITY": "1"},
                "connections": {"TRG": [2]}},
        "comb": {"type": "$check", "parameters": {"TRG_ENABLE": "0" * 32, "TRG_POLARITY": ""},
                 "connections": {"TRG": []}},
        "gate": {"type": "$_SDFFE_PN0P_", "parameters": {}, "connections": {"C": [2]}},  # no CLK port
        "gff": {"type": "$_DFFE_PP_", "parameters": {}, "connections": {"CLK": [2]}},
    }
    assert common.clock_problems(_probe(tmp_path, ok), "m", "clk") == []
    bad = {
        "mem": {"type": "$mem_v2", "parameters": {"WR_CLK_ENABLE": "11", "WR_CLK_POLARITY": "10"},
                "connections": {"WR_CLK": [2, 3]}},          # port 0 on clk falling, port 1 on c2
        "rd": {"type": "$memrd_v2", "parameters": {"CLK_ENABLE": "1", "CLK_POLARITY": "1"},
               "connections": {"CLK": ["0"]}},                # a clock tied to a constant
        "x": {"type": "$dff", "parameters": {"CLK_POLARITY": "x"}, "connections": {"CLK": [2]}},
        "gneg": {"type": "$_DFF_N_", "parameters": {}, "connections": {"CLK": [2]}},
        "gbad": {"type": "$_DFF_Q_", "parameters": {}, "connections": {"CLK": [2]}},
    }
    probs = common.clock_problems(_probe(tmp_path, bad), "m", "clk")
    assert any("WR_CLK is the falling edge of clk" in p for p in probs)
    assert any("WR_CLK is c2, not clk" in p for p in probs)
    assert any("CLK is constant 0" in p for p in probs)
    assert any("$_DFF_N_ gneg: CLK is the falling edge" in p for p in probs)
    assert sum("cannot read" in p for p in probs) == 2   # x polarity; unknown gate-level edge
    assert len(probs) == 6


def test_clock_problems_fails_closed_on_a_bad_probe(tmp_path):
    assert common.clock_problems(tmp_path / "missing.json", "m", "clk")
    wide = {"clk": {"direction": "input", "bits": [2, 3]}}
    assert common.clock_problems(_probe(tmp_path, {}, wide), "m", "clk")


# --------------------------------------------------------------------------------------------------
# Finding 2: --json stdout is exactly one JSON document


@needs_tools
def test_bmc_json_stdout_is_one_document_without_reset(tmp_path, capsys):
    f = _v(tmp_path, NO_RESET)
    rc = _rc(["formal", "bmc", "--verilog", str(f), "--top", "SingleClock", "--depth", "4",
              "--out", str(tmp_path / "o"), "--json"])
    cap = capsys.readouterr()
    r = json.loads(cap.out)   # the whole of stdout
    assert rc == 1 and r["status"] == "fail" and r["reset"] is None
    assert "no reset input" in cap.err


@needs_tools
@pytest.mark.parametrize("flow", ["bmc", "xprop"])
def test_json_stdout_is_one_document(tmp_path, capsys, flow):
    f = _v(tmp_path, ONE)
    extra = ["--outputs"] if flow == "xprop" else []
    _rc(["formal", flow, "--verilog", str(f), "--top", "one", "--depth", "6", "--out", str(tmp_path / "o"),
         "--json", *extra])
    out = capsys.readouterr().out
    assert json.loads(out) == json.loads((tmp_path / "o" / "result.json").read_text())
