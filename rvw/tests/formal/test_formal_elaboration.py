"""Round-16 regressions: proof wrappers must use the elaborated port types."""
import json
import shutil

import pytest

from rvw.cli import main
from rvw.formal import common

needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("yosys", "sby", "yices-smt2")),
    reason="needs yosys, sby and yices-smt2",
)


def run(tmp_path, text, flow="bmc", extra=()):
    rtl = tmp_path / "top.sv"
    rtl.write_text(text)
    out = tmp_path / "out"
    rc = main(["formal", flow, "--verilog", str(rtl), "--top", "top", "--depth", "6",
               "--timeout", "30", "--out", str(out), *extra])
    return rc, json.loads((out / "result.json").read_text()), out


@needs_tools
@pytest.mark.parametrize("decl,limit,width", [
    ("integer", 2, 32), ("[1:0][1:0]", 4, 4),
    ("signed [31:0]", 2, 32), ("[W-1:0]", 4, 5),
])
def test_bmc_keeps_every_elaborated_input_bit(tmp_path, decl, limit, width):
    rc, result, out = run(tmp_path, f"""module top #(parameter W=5)(input clk, input {decl} d);
        always @(posedge clk) assert(d < {limit}); endmodule""")
    assert rc == 1 and result["status"] == "fail"
    wrapper = (out / "rvw_formal_top.sv").read_text()
    assert f"[{width - 1}:0] d" in wrapper
    if decl.startswith(("integer", "signed")):
        assert f"input signed [{width - 1}:0] d" in wrapper


@needs_tools
@pytest.mark.parametrize("decl", ["integer", "[1:0][1:0]"])
def test_xprop_keeps_high_input_bits_free(tmp_path, decl):
    limit = 2 if decl == "integer" else 4
    rc, result, _ = run(tmp_path, f"""module top(input clk, input {decl} d, output reg y);
        reg q;
        always @(posedge clk) begin q <= !q; if (d >= {limit}) y <= q; else y <= 0; end
        endmodule""", "xprop", ["--outputs"])
    assert rc == 1 and result["status"] == "fail"
    assert [x["signal"] for x in result["x_reaches"]] == ["y"]


@needs_tools
@pytest.mark.parametrize("flow", ["bmc", "xprop"])
def test_port_probe_uses_the_proof_defines(tmp_path, flow):
    rc, result, out = run(tmp_path, """module top(input clk,
        `ifdef SYNTHESIS
        input [3:0] d,
        `else
        input integer d,
        `endif
        output reg y);
        reg q;
        always @(posedge clk) begin
            q <= !q; y <= d >= 2 ? q : 0;
            assert(d < 2);
        end
        endmodule""", flow, ["--outputs"] if flow == "xprop" else [])
    assert rc == 1 and result["status"] == "fail"
    name = "rvw_xprop_top.sv" if flow == "xprop" else "rvw_formal_top.sv"
    width = 4 if flow == "xprop" else 32
    assert f"[{width - 1}:0] d" in (out / name).read_text()


@needs_tools
def test_non_ansi_ports_and_signed_values(tmp_path):
    rc, result, out = run(tmp_path, """module top(clk, d);
        input clk; input signed [7:3] d;
        always @(posedge clk) assert(d >= 0);
        endmodule""")
    assert rc == 1 and result["status"] == "fail"
    assert "input signed [4:0] d" in (out / "rvw_formal_top.sv").read_text()


@needs_tools
def test_from_sim_ties_use_elaborated_widths(tmp_path):
    rtl = tmp_path / "top.sv"
    rtl.write_text("module top(input clk, input integer d); always @(posedge clk) assert(d<2); endmodule")
    trace = tmp_path / "t.vcd"
    trace.write_text("""$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var wire 32 " d $end
$upscope $end
$enddefinitions $end
#0
0!
b0 "
#5
1!
#10
0!
""")
    out = tmp_path / "out"
    rc = main(["formal", "from-sim", "--verilog", str(rtl), "--top", "top", "--trace", str(trace),
               "--scope", "top", "--time", "5", "--tie", "d=256", "--depth", "4", "--out", str(out)])
    result = json.loads((out / "result.json").read_text())
    assert rc == 1 and result["status"] == "fail"
    assert "connect -nounset -set d 32'd256" in (out / "from_sim.sby").read_text()


@pytest.mark.parametrize("port", [
    {}, {"direction": "input", "bits": []}, {"direction": "unknown", "bits": [2]},
    {"direction": "input", "bits": [None]}, {"direction": "input", "bits": [True]},
    {"direction": "input", "bits": [2], "signed": "1"},
])
def test_port_metadata_must_be_complete(tmp_path, port):
    path = tmp_path / "ports.json"
    path.write_text(json.dumps({"modules": {"top": {"ports": {"d": port}}}}))
    with pytest.raises(SystemExit) as e:
        common.ports_from_json(path, "top")
    assert e.value.code == 2


@pytest.mark.parametrize("rc", [1, common.TIMEOUT_EXIT])
def test_failed_port_probe_cannot_read_stale_metadata(tmp_path, monkeypatch, rc, probe_ports):
    path = tmp_path / "module_ports.json"
    path.write_text(json.dumps({"modules": {"top": {"ports": {"clk": {"direction": "input", "bits": [2]}}}}}))
    monkeypatch.setattr(common, "need", lambda _: "yosys")
    monkeypatch.setattr(common, "run", lambda *a, **kw: (rc, 0.0))
    with pytest.raises(SystemExit) as e:
        probe_ports([], "top", tmp_path, 1)
    assert e.value.code == 2 and not path.exists()


@needs_tools
@pytest.mark.parametrize("ports", ["input [1:0] clk", "input clk, input [1:0] reset", "input clk, inout d"])
def test_unsupported_wrapper_connections_are_refused(tmp_path, ports):
    rtl = tmp_path / "top.sv"
    rtl.write_text(f"module top({ports}); always @(posedge clk) assert(1); endmodule")
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as e:
        main(["formal", "bmc", "--verilog", str(rtl), "--top", "top", "--depth", "4", "--out", str(out)])
    assert e.value.code == 2 and not (out / "result.json").exists()
