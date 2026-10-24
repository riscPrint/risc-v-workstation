"""Round-16 regressions for undriven state and uninitialized flip-flops."""
import json
import shutil

import pytest

from rvw.cli import main
from rvw.common.proc import run_group

needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("yosys", "sby", "yices-smt2")),
    reason="needs yosys, sby and yices-smt2",
)


@needs_tools
@pytest.mark.parametrize("body", [
    "reg q; assign y=q;",
    "wire q; assign y=q;",
    "wire [1:0] q; assign q[0]=0; assign y=q[1];",
    "child u(.y(y));",
])
def test_xprop_unwritten_register_is_unknown(tmp_path, body):
    rtl = tmp_path / "top.sv"
    rtl.write_text(f"module top(input clk, output y); {body} endmodule\n"
                   "module child(output y); reg q; assign y=q; endmodule")
    out = tmp_path / "out"
    rc = main(["formal", "xprop", "--verilog", str(rtl), "--top", "top", "--outputs",
               "--depth", "6", "--out", str(out)])
    result = json.loads((out / "result.json").read_text())
    assert rc == 1 and result["status"] == "fail"
    assert [x["signal"] for x in result["x_reaches"]] == ["y"]


@needs_tools
@pytest.mark.parametrize("body,expected", [
    ("reg q; always @(posedge clk) q<=!q; assign y=q;", "fail"),
    ("reg q; always @(posedge clk) if (d) q<=1; assign y=q;", "fail"),
    ("reg q; always @(posedge clk) q<=d; assign y=q;", "pass"),
    ("reg q=0; assign y=q;", "pass"),
    ("reg q=0; always @(posedge clk) q<=!q; assign y=q;", "pass"),
    ("wire [1:0] q; assign q[0]=0; assign y=q[0];", "pass"),
    ("assign y=d;", "pass"),
])
def test_xprop_keeps_uninitialized_state_unknown_until_written(tmp_path, body, expected):
    rtl = tmp_path / "top.sv"
    rtl.write_text(f"module top(input clk, input d, output y); {body} endmodule")
    out = tmp_path / "out"
    rc = main(["formal", "xprop", "--verilog", str(rtl), "--top", "top", "--outputs",
               "--depth", "6", "--out", str(out)])
    result = json.loads((out / "result.json").read_text())
    assert result["status"] == expected
    assert rc == (0 if expected == "pass" else 1)
    if expected == "pass":
        assert result["reachability"]["status"] == "reachable"


@needs_tools
@pytest.mark.parametrize("flow", ["bmc", "from-sim"])
@pytest.mark.parametrize("body", ["reg q;", "reg q=0; always @(posedge clk) q<=!q;"])
def test_missing_or_undriven_state_is_free_in_two_state_proofs(tmp_path, flow, body):
    rtl = tmp_path / "top.sv"
    # For replay, the waveform omits q. Even its RTL initializer must not constrain it.
    rtl.write_text(f"module top(input clk); {body} always @(posedge clk) assert(q==0); endmodule")
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
    extra = ["--trace", str(trace), "--scope", "top", "--time", "5"] if flow == "from-sim" else []
    out = tmp_path / "out"
    rc = main(["formal", flow, "--verilog", str(rtl), "--top", "top", "--depth", "6",
               "--out", str(out), *extra])
    result = json.loads((out / "result.json").read_text())
    assert rc == 1 and result["status"] == "fail"
    if flow == "from-sim" and "always" in body:
        assert result["state"]["ff_bits_free"] == 1


@needs_tools
def test_unwritten_register_matches_four_state_simulation(tmp_path):
    if not shutil.which("iverilog") or not shutil.which("vvp"):
        pytest.fail("the four-state regression needs iverilog and vvp")
    rtl = tmp_path / "top.sv"
    rtl.write_text("module top(input clk, output y); reg q; assign y=q; endmodule")
    tb = tmp_path / "tb.sv"
    tb.write_text("""module tb;
    reg clk=0; wire y;
    top dut(clk,y);
    always #5 clk=~clk;
    initial begin
        repeat (6) @(posedge clk);
        $display("y=%b unknown=%b", y, $isunknown(y));
        $finish;
    end
    endmodule
    """)
    binary = tmp_path / "sim"
    built = run_group(["iverilog", "-g2012", "-s", "tb", "-o", str(binary), str(rtl), str(tb)],
                      capture=True, timeout=30)
    assert not built.timed_out and built.returncode == 0, built.stdout
    sim = run_group(["vvp", str(binary)], capture=True, timeout=30)
    assert not sim.timed_out and sim.returncode == 0
    assert "y=x unknown=1" in sim.stdout
    out = tmp_path / "out"
    rc = main(["formal", "xprop", "--verilog", str(rtl), "--top", "top", "--outputs",
               "--depth", "6", "--out", str(out)])
    result = json.loads((out / "result.json").read_text())
    assert rc == 1 and result["status"] == "fail"
