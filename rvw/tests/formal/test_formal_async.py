"""Round-16 follow-up: inter-edge state events cannot use the single-clock model."""
import json
import shutil

import pytest

from rvw.cli import main
from rvw.formal import common

needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("yosys", "sby", "yices-smt2")),
    reason="needs yosys, sby and yices-smt2",
)

# /tmp/review16-proof/async-reset-auto.py: an rst pulse between rising edges clears q
# without clearing r. With multiclock off BMC incorrectly proved q == r at depth 8.
REVIEW_DUT = """module dut(input clk,input rst,output reg q=0,output reg r=0);
always @(posedge clk or posedge rst) if(rst) q<=0; else q<=!q;
always @(posedge clk) if(rst) r<=0; else r<=!r;
endmodule
module top(input clk,input rst,output q,output r);
dut d(clk,rst,q,r);
always @(posedge clk) if (!rst) assert(q == r);
endmodule
"""


def invoke(tmp_path, text, flow, extra=()):
    rtl = tmp_path / "top.sv"
    rtl.write_text(text)
    trace = tmp_path / "trace.vcd"
    trace.write_text("""$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$upscope $end
$enddefinitions $end
#0
0!
#5
1!
#10
0!
""")
    out = tmp_path / "out"
    out.mkdir()
    (out / "result.json").write_text('{"status":"pass"}')
    options = ["--outputs"] if flow == "xprop" else []
    if flow == "from-sim":
        options = ["--trace", str(trace), "--scope", "top", "--time", "5"]
    try:
        rc = main(["formal", flow, "--verilog", str(rtl), "--top", "top", "--depth", "8",
                   "--timeout", "30", "--out", str(out), "--json", *options, *extra])
    except SystemExit as exc:
        rc = exc.code
    return rc, out


@needs_tools
@pytest.mark.parametrize("flow", ["bmc", "from-sim", "xprop"])
def test_review_async_reset_design_is_refused(tmp_path, capsys, flow):
    extra = ["--reset", "rst"] + (["--free-reset"] if flow == "bmc" else [])
    rc, out = invoke(tmp_path, REVIEW_DUT, flow, extra)
    captured = capsys.readouterr()
    assert rc == 2, captured.out
    assert not (out / "result.json").exists()
    assert "asynchronous" in captured.err and "$adff" in captured.err
    assert not (out / "sby.log").exists()
    assert not (out / "state.vcd").exists()


@needs_tools
@pytest.mark.parametrize("flow", ["bmc", "from-sim", "xprop"])
@pytest.mark.parametrize("body", [
    "always @(posedge clk or posedge rst) if(rst) q<=d; else q<=!q;",  # async load
    "always @(posedge clk or posedge rst or posedge set) "
    "if(set) q<=1; else if(rst) q<=0; else q<=d;",  # async set/clear
    "always @* if(en) q<=d;",  # latch
    "always @* if(rst) q<=0; else if(en) q<=d;",  # resettable latch
    # Dead output and an inactive instance reset must not remove the async cell before the check.
    "wire unused; child c(clk,1'b0,d,unused); always @(posedge clk) q<=d;",
])
def test_all_flows_refuse_async_state_before_optimization(tmp_path, capsys, flow, body):
    text = ("module top(input clk,rst,set,en,d,output reg q); " + body
            + " always @(posedge clk) assert(1); endmodule\n"
            + "module child(input clk,rst,d,output reg q); "
              "always @(posedge clk or posedge rst) if(rst) q<=0; else q<=d; endmodule")
    rc, out = invoke(tmp_path, text, flow)
    assert rc == 2 and not (out / "result.json").exists()
    assert "asynchronous" in capsys.readouterr().err


@needs_tools
def test_state_probe_uses_xprop_defines(tmp_path, capsys):
    rc, out = invoke(tmp_path, """module top(input clk,rst,d,output reg q);
    `ifdef SYNTHESIS
    always @(posedge clk or posedge rst) if(rst) q<=0; else q<=d;
    `else
    always @(posedge clk) q<=d;
    `endif
    endmodule""", "xprop")
    assert rc == 2 and not (out / "result.json").exists()
    assert "$adff" in capsys.readouterr().err


def modules(kind, connections=None):
    return {"top": {"cells": {"state": {"type": kind, "connections": connections or {}}}}}


@pytest.mark.parametrize("kind", [
    "$adff", "$adffe", "$aldff", "$aldffe", "$dffsr", "$dffsre", "$sr",
    "$dlatch", "$adlatch", "$dlatchsr", "$ff", "$future_ff",
    "$_DFF_PP0_", "$_DFFE_PN1P_", "$_ALDFF_PP_", "$_ALDFFE_PPP_",
    "$_DFFSR_PPP_", "$_DFFSRE_PPPP_", "$_SR_PP_", "$_DLATCH_P_",
    "$_DLATCH_PP0_", "$_DLATCHSR_PPP_",
])
def test_word_and_fine_grained_async_state_cells_are_refused(kind):
    problems = common.async_state_problems(modules(kind))
    assert len(problems) == 1 and kind in problems[0]


@pytest.mark.parametrize("kind", ["$dff", "$dffe", "$sdff", "$sdffe", "$sdffce",
                                 "$memrd", "$memwr_v2", "$meminit_v2"])
def test_synchronous_state_and_async_memory_reads_are_supported(kind):
    assert common.async_state_problems(modules(kind)) == []


@pytest.mark.parametrize("kind,port", [("$memrd_v2", "ARST"), ("$mem_v2", "RD_ARST")])
@pytest.mark.parametrize("bits", [[2], ["1"], ["x"], [], None])
def test_async_memory_reset_must_be_tied_inactive(kind, port, bits):
    assert common.async_state_problems(modules(kind, {port: bits}))
    assert common.async_state_problems(modules(kind, {port: ["0"]})) == []


@pytest.mark.parametrize("data", [{}, {"modules": {}}, {"modules": {"top": {}}},
                                  {"modules": {"top": {"cells": {"bad": {}}}}}])
def test_state_probe_fails_closed_on_missing_metadata(tmp_path, data):
    path = tmp_path / "probe.json"
    path.write_text(json.dumps(data))
    with pytest.raises(SystemExit) as exc:
        common.check_state_controls(path)
    assert exc.value.code == 2
