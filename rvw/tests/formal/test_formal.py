"""Tests for `rvw formal` on tiny hand-written designs (Verilator, yosys and sby from oss-cad-suite)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.formal import common, flows, vcdsnap

TOOLS = all(shutil.which(t) for t in ("verilator", "yosys", "sby", "vcd2fst", "fst2vcd"))
needs_tools = pytest.mark.skipif(not TOOLS, reason="needs verilator, yosys, sby (source spinal-boom/env.sh)")

DUT = """\
module dut (
  input  wire          clk,
  input  wire          reset,
  input  wire [2:0]    waddr,
  input  wire [7:0]    wdata,
  input  wire          we,
  input  wire [2:0]    raddr,
  output reg  [7:0]    rdata,
  output reg  [15:0]   cnt
);
  reg [7:0] mem [0:4];
  // a bug 1005 cycles deep, and a property of the memory contents (writes only work early on)
  wire chk_deep = !reset && cnt == 16'd1005;
  wire chk_mem = !reset && cnt > 16'd1000 && mem[1] == 8'd4;
  always @(posedge clk) begin
    if (reset) cnt <= 0; else cnt <= cnt + 1;
    if (we && waddr < 5 && cnt < 16'd100) mem[waddr] <= wdata;
    rdata <= mem[raddr];
`ifdef FORMAL
    assert((! chk_deep));
    assert((! chk_mem));
`endif
  end
endmodule
"""

TB = """\
module tb;
  reg clk = 0, reset = 1; reg [2:0] waddr = 0, raddr = 0; reg [7:0] wdata = 0; reg we = 0;
  wire [7:0] rdata; wire [15:0] cnt;
  dut dut(.clk(clk), .reset(reset), .waddr(waddr), .wdata(wdata), .we(we), .raddr(raddr), .rdata(rdata), .cnt(cnt));
  always #5 clk = ~clk;
  integer i;
  initial begin
    $dumpfile("t.fst"); $dumpvars(0, tb);
    #20 reset = 0;
    for (i = 0; i < 20; i = i + 1) begin @(negedge clk); we = 1; waddr = i % 5; wdata = i * 3 + 1; raddr = (i + 1) % 5; end
    @(negedge clk); we = 0;
    #10000 $finish;
  end
endmodule
"""


@pytest.fixture(scope="module")
def sim(tmp_path_factory):
    """A Verilator FST of `dut`: mem[1] holds 4 (written at i=1, overwritten at i=6 by 19 ... see below)."""
    d = tmp_path_factory.mktemp("sim")
    (d / "dut.v").write_text(DUT)
    (d / "tb.v").write_text(TB)
    subprocess.run(["verilator", "--binary", "--trace-fst", "--timing", "-Wno-fatal", "tb.v", "dut.v", "--top", "tb",
                    "-o", "sim"], cwd=d, check=True, capture_output=True)
    subprocess.run(["./obj_dir/sim"], cwd=d, check=True, capture_output=True)
    return d


@needs_tools
def test_module_ports(tmp_path, probe_ports):
    (tmp_path / "dut.v").write_text(DUT)
    ports = probe_ports([tmp_path / "dut.v"], "dut", tmp_path)
    assert [(p.name, p.direction, p.width) for p in ports][:4] == [
        ("clk", "input", 1), ("reset", "input", 1), ("waddr", "input", 3), ("wdata", "input", 8)]
    assert ports[-1].name == "cnt" and ports[-1].width == 16


def test_wrapper_holds_reset_then_releases():
    ports = [common.Port("clk", "input", 1), common.Port("reset", "input", 1), common.Port("a", "input", 4),
             common.Port("y", "output", 2)]
    w = flows.wrapper("dut", ports, "clk", "reset", True, 2, False)
    assert "rvw_cycle < 8'd2" in w and ".reset(rvw_reset)" in w and "input [3:0] a" in w and "wire [1:0] y;" in w


@needs_tools
def test_snapshot_hoists_memories_and_counts_edges(sim):
    snap = vcdsnap.take(sim / "t.fst", "tb.dut", "clk", cycle=100, time=None)
    assert snap.memories == ["mem"]
    vals = {".".join(v.path): snap.values.get(v.code) for v in snap.vars}
    # 2 cycles of reset, then cnt counts: the 100th rising edge (t=995) leaves cnt = 98
    assert int(vals["cnt"][1:], 2) == 98
    assert "mem[0]" in vals and vals["mem[0]"].startswith("b")


def _from_sim(sim, out, *extra):
    rc = main(["formal", "from-sim", "--verilog", str(sim / "dut.v"), "--top", "dut", "--trace", str(sim / "t.fst"),
               "--cycle", "993", "--depth", "20", "--out", str(out), *extra])
    return rc, json.loads((out / "result.json").read_text())


@needs_tools
def test_from_sim_finds_deep_failure(sim, tmp_path, monkeypatch):
    # cnt == 1005 happens 1005 cycles after reset: too deep for BMC from reset, 14 cycles from cycle 993.
    # mem[1] was last written with 49 (i = 16), so chk_mem cannot fire from the traced state.
    conversions = []
    run = vcdsnap.run_group

    def count_conversion(argv, **kwargs):
        conversions.append(argv)
        return run(argv, **kwargs)

    monkeypatch.setattr(vcdsnap, 'run_group', count_conversion)
    rc, r = _from_sim(sim, tmp_path / "fs")
    assert len(conversions) == 1  # scope selection and state extraction share one decoded FST
    assert rc == 1 and r["status"] == "fail" and r["scope"] == "tb.dut"
    st = r["state"]
    assert st["mem_init"] == 1 and st["mem_bits_from_trace"] == st["mem_bits"] == 40
    assert st["ff_bits_free"] == 0 and st["ff_bits_from_trace"] + st["ff_bits_flow"] == st["ff_bits"]
    assert [f["fail_signal"] for f in r["failures"]] == ["chk_deep"]
    (f,) = r["failures"]
    # the state of cycle 993 has cnt = 991 (two reset cycles); cnt == 1005 at step 14, flagged at step 15
    assert f["step"] == 15 and f["cycle"] == 993 + 14


@needs_tools
def test_from_sim_free_memories_lose_the_state(sim, tmp_path):
    rc, r = _from_sim(sim, tmp_path / "free", "--memories", "free")
    assert r["state"]["mem_init"] == 0
    assert sorted(f["fail_signal"] for f in r["failures"]) == ["chk_deep", "chk_mem"]


@needs_tools
def test_bmc_from_reset_cannot_reach_it(sim, tmp_path):
    rc = main(["formal", "bmc", "--verilog", str(sim / "dut.v"), "--top", "dut", "--depth", "15",
               "--out", str(tmp_path / "bmc")])
    assert rc == 0 and json.loads((tmp_path / "bmc" / "result.json").read_text())["status"] == "pass"


@needs_tools
def test_xprop_finds_uninitialized_memory_read(sim, tmp_path):
    rc = main(["formal", "xprop", "--verilog", str(sim / "dut.v"), "--top", "dut", "--outputs", "--depth", "6",
               "--out", str(tmp_path / "x")])
    r = json.loads((tmp_path / "x" / "result.json").read_text())
    assert rc == 1 and [x["signal"] for x in r["x_reaches"]] == ["rdata"]


TIE = """\
module sub(input clk, input v, output reg r, output o); assign o = v; always @(posedge clk) r <= v; endmodule
module tietop (
  input  wire clk,
  input  wire reset,
  input  wire v,
  output wire o,
  output wire r
);
  sub s(.clk(clk), .v(v), .o(o), .r(r));
`ifdef FORMAL
  always @(posedge clk) if (!reset) assert(!o);
`endif
endmodule
"""


@needs_tools
def test_tie_reaches_through_submodules(tmp_path):
    # `connect -set` without -nounset would drop the aliases of the tied net (o = s.o = v), leaving the
    # submodule's view of it free: the tie must hold everywhere.
    (tmp_path / "t.v").write_text(TIE)
    (tmp_path / "tb.v").write_text(
        "module tb; reg clk=0, reset=1, v=0; wire o, r; tietop top(.clk(clk),.reset(reset),.v(v),.o(o),.r(r));\n"
        "always #5 clk=~clk; initial begin $dumpfile(\"t.fst\"); $dumpvars(0,tb); #20 reset=0; #100 $finish; end endmodule\n")
    subprocess.run(["verilator", "--binary", "--trace-fst", "--timing", "-Wno-fatal", "tb.v", "t.v", "--top", "tb",
                    "-o", "sim"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["./obj_dir/sim"], cwd=tmp_path, check=True, capture_output=True)
    base = ["formal", "from-sim", "--verilog", str(tmp_path / "t.v"), "--top", "tietop", "--trace",
            str(tmp_path / "t.fst"), "--scope", "tb.top", "--cycle", "5", "--depth", "4"]
    assert main(base + ["--tie", "v=0", "--out", str(tmp_path / "tied")]) == 0
    assert main(base + ["--out", str(tmp_path / "free")]) == 1
    assert main(base + ["--tie", "v=1", "--out", str(tmp_path / "conflict")]) == 1
    r = json.loads((tmp_path / "conflict" / "result.json").read_text())
    assert r["tie_conflicts"] == [{"port": "v", "tie": 1, "traced": 0}]


@needs_tools
def test_mcp_tools_match_the_cli(sim, tmp_path):
    from rvw.mcp.registry import Registry
    registry, problems = Registry.discover({"formal"})
    assert not problems
    try:
        assert {"formal_bmc", "formal_from_sim", "formal_xprop"} <= set(registry.tools)
        _, started, error = registry.call_json("formal_xprop", {
            "verilog": [str(sim / "dut.v")], "top": "dut", "outputs": True, "depth": 6, "out": str(tmp_path / "x")})
        assert not error and "job_id" in started
        _, status, error = registry.call_json("job_status", {"job_id": started["job_id"], "wait_s": 60})
        assert not error and status["status"] == "done", status
        assert [x["signal"] for x in status["result"]["x_reaches"]] == ["rdata"]
    finally:
        registry.jobs.shutdown()


# `q` and `m[0]` start at 0 (RTL initial values) and are set to 1 after reset: the asserts hold at time 0
# but not at the traced cycle.
INIT_DUT = """\
module idut(input clk, input reset, input set, input [1:0] wa, output reg q, output [7:0] r);
  reg [7:0] m [0:3];
  initial q = 0;
  initial begin m[0] = 0; m[1] = 0; m[2] = 0; m[3] = 0; end
  assign r = m[0];
  always @(posedge clk) begin
    if (reset) q <= 0; else if (set) q <= 1;
    if (!reset && set) m[wa] <= 8'd1;
`ifdef FORMAL
    if (!reset) assert(q == 0);
    if (!reset) assert(m[0] == 8'd0);
`endif
  end
endmodule
"""

INIT_TB = """\
module tb;
  reg clk = 0, reset = 1, set = 0; reg [1:0] wa = 0; wire q; wire [7:0] r;
  idut dut(clk, reset, set, wa, q, r);
  always #5 clk = ~clk;
  initial begin
    $dumpfile("full.vcd"); $dumpvars(0, tb);
    #20 reset = 0; set = 1;
    #20 set = 0;
    #100 $finish;
  end
endmodule
"""


def _drop_vars(src: Path, dst: Path, drop) -> None:
    """Copy a VCD without the variables whose reference `drop(ref)` accepts (and their value changes)."""
    lines = src.read_text().splitlines()
    codes = {ln.split()[3] for ln in lines if ln.strip().startswith("$var ") and drop(ln.split()[4])}
    assert codes
    keep = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("$var ") and s.split()[3] in codes:
            continue
        if s[:1] in "01xzXZ" and s[1:] in codes:
            continue
        if s[:1] in "bBrR" and len(s.split()) == 2 and s.split()[1] in codes:
            continue
        keep.append(ln)
    dst.write_text("\n".join(keep) + "\n")


@pytest.fixture(scope="module")
def init_sim(tmp_path_factory):
    d = tmp_path_factory.mktemp("initsim")
    (d / "dut.v").write_text(INIT_DUT)
    (d / "tb.v").write_text(INIT_TB)
    subprocess.run(["verilator", "--binary", "--trace", "--timing", "-Wno-fatal", "tb.v", "dut.v", "--top", "tb",
                    "-o", "sim"], cwd=d, check=True, capture_output=True)
    subprocess.run(["./obj_dir/sim"], cwd=d, check=True, capture_output=True)
    _drop_vars(d / "full.vcd", d / "no_q.vcd", lambda ref: ref == "q")
    _drop_vars(d / "full.vcd", d / "no_m.vcd", lambda ref: ref == "m" or ref.startswith("m["))
    return d


def _init_run(d: Path, trace: str, out: Path):
    rc = main(["formal", "from-sim", "--verilog", str(d / "dut.v"), "--top", "idut", "--trace", str(d / trace),
               "--scope", "tb.dut", "--cycle", "8", "--depth", "4", "--tie", "set=0", "--out", str(out)])
    return rc, json.loads((out / "result.json").read_text())


@needs_tools
def test_from_sim_state_missing_from_trace_starts_free(init_sim, tmp_path):
    full = _init_run(init_sim, "full.vcd", tmp_path / "full")
    no_q = _init_run(init_sim, "no_q.vcd", tmp_path / "no_q")
    no_m = _init_run(init_sim, "no_m.vcd", tmp_path / "no_m")
    # Full trace: q = 1 and m[0] = 1 at cycle 8, both asserts fail.
    assert full[0] == 1 and full[1]["status"] == "fail" and len(full[1]["failures"]) == 2
    # Without q (or the memory) in the trace, it must start free (any value), not at its RTL initial 0:
    # never a pass.
    for (rc, r), line in ((no_q, ":10"), (no_m, ":11")):
        assert rc == 1 and r["status"] == "fail"
        assert any(f["location"].endswith(line) for f in r["failures"]), r["failures"]
    st = full[1]["state"]
    assert st["ff_bits_free"] == 0 and st["ff_bits_from_trace"] == 1 and st["mem_init"] == 1
    st = no_q[1]["state"]
    assert st["ff_bits_from_trace"] == 0 and st["ff_bits_free"] == 1 and st["registers_free"] == ["idut.q"]
    st = no_m[1]["state"]
    assert st["mem_init"] == 0 and st["mem_bits_from_trace"] == 0 and st["mems_uninit"] == ["idut.m"]


def test_state_coverage_counts_bits_by_source(tmp_path):
    il = tmp_path / "s.il"
    il.write_text("""module \\top
  attribute \\init 4'01x1
  wire width 4 \\a
  wire width 2 \\b
  attribute \\init 1'0
  attribute \\rvw_flow_init 1
  wire \\en
  attribute \\init 0
  wire width 32 \\w
  cell $dff $d1
    parameter \\WIDTH 4
    connect \\Q \\a
  end
  cell $dff $d2
    parameter \\WIDTH 3
    connect \\Q { \\b \\a [1] }
  end
  cell $dff $d3
    parameter \\WIDTH 1
    connect \\Q \\en
  end
  cell $dff $d4
    parameter \\WIDTH 32
    connect \\Q \\w
  end
  cell $mem_v2 $m
    parameter \\MEMID "\\\\mem"
    parameter \\SIZE 2
    parameter \\WIDTH 4
    parameter \\INIT 8'x1x0xxxx
  end
end
""")
    st = flows.state_coverage(il)
    # a: 3 known bits + 1 x; b: free (2); a[1] is the x bit; en: flow; w: integer init 0 (32 known bits)
    assert st["ff_bits"] == 40 and st["ff_bits_flow"] == 1
    assert st["ff_bits_from_trace"] == 3 + 32 and st["ff_bits_free"] == 1 + 2 + 1
    assert st["registers_free"] == ["top.a", "top.a", "top.b"]
    assert st["mem_bits"] == 8 and st["mem_bits_from_trace"] == 2 and st["mem_init"] == 1


SMALL_VCD = """$timescale 1ps $end
$scope module tb $end
$scope module dut $end
$var wire 1 ! clk $end
$var wire 4 " q $end
$upscope $end
$upscope $end
$enddefinitions $end
#5
$dumpvars
0!
b0000 "
$end
#10
1!
b0011 "
#20
0!
"""


def test_snapshot_time_must_be_inside_the_trace(tmp_path, capsys):
    vcd = tmp_path / "t.vcd"
    vcd.write_text(SMALL_VCD)
    snap = vcdsnap.take(vcd, "tb.dut", "clk", cycle=None, time=20)  # the last timestamp is recorded
    assert snap.time == 20
    snap = vcdsnap.take(vcd, "tb.dut", "clk", cycle=None, time=12)
    assert snap.values['"'] == "b0011"
    for t in (21, 100000):
        with pytest.raises(SystemExit) as e:
            vcdsnap.take(vcd, "tb.dut", "clk", cycle=None, time=t)
        assert e.value.code == 2
        assert "times 5..20" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        vcdsnap.take(vcd, "tb.dut", "clk", cycle=None, time=4)
    assert "first recorded time of the trace (5)" in capsys.readouterr().err


@needs_tools
def test_from_sim_time_past_the_trace_is_rejected(init_sim, tmp_path):
    out = tmp_path / "late"
    with pytest.raises(SystemExit) as e:
        main(["formal", "from-sim", "--verilog", str(init_sim / "dut.v"), "--top", "idut", "--trace",
              str(init_sim / "full.vcd"), "--scope", "tb.dut", "--time", "100000", "--depth", "4", "--out", str(out)])
    assert e.value.code == 2 and not (out / "result.json").exists()
