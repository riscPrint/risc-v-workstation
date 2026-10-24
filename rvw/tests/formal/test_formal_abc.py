"""ABC bmc3 must refuse an optimized combinational model with a useful remedy."""
import json
import shutil

import pytest

from rvw.cli import main
from rvw.formal import common


needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("yosys", "sby", "yosys-abc", "yices-smt2")),
    reason="needs oss-cad-suite tools",
)


@needs_tools
def test_bmc3_combinational_model_is_refused(tmp_path, capsys):
    source = tmp_path / "top.sv"
    source.write_text("module top(input clk); always @(posedge clk) assert(1); endmodule\n")
    out = tmp_path / "out"
    # A rerun must also remove any earlier verdict before refusing this configuration.
    out.mkdir()
    (out / "result.json").write_text('{"status":"pass"}\n')
    with pytest.raises(SystemExit) as exc:
        main(["formal", "bmc", "--verilog", str(source), "--top", "top", "--depth", "4",
              "--engine", "abc:bmc3", "--out", str(out)])
    assert exc.value.code == 2
    message = capsys.readouterr().err
    assert "abc:bmc3" in message and "combinational" in message
    assert "--engine smtbmc:yices" in message
    assert not (out / "result.json").exists()
    assert "Does not work for combinational networks" in (out / "sby/logfile.txt").read_text()
    # The suggested engine earns a pass, including the separate reachability check.
    assert main(["formal", "bmc", "--verilog", str(source), "--top", "top", "--depth", "4",
                 "--engine", "smtbmc:yices", "--out", str(out)]) == 0
    result = json.loads((out / "result.json").read_text())
    assert result["status"] == "pass" and result["reachability"]["status"] == "reachable"


@needs_tools
@pytest.mark.parametrize("limit, expected", [(7, "pass"), (2, "fail")])
def test_bmc3_sequential_model_keeps_its_verdict(tmp_path, limit, expected):
    source = tmp_path / "top.sv"
    source.write_text(f"""module top(input clk);
      reg [3:0] count = 0;
      always @(posedge clk) begin count <= count + 1; assert(count < {limit}); end
    endmodule
    """)
    out = tmp_path / "out"
    rc = main(["formal", "bmc", "--verilog", str(source), "--top", "top", "--depth", "6",
               "--engine", "abc:bmc3", "--out", str(out)])
    result = json.loads((out / "result.json").read_text())
    assert rc == (0 if expected == "pass" else 1)
    assert result["status"] == expected
    if expected == "pass":
        assert result["reachability"]["status"] == "reachable"


def test_unrelated_engine_error_stays_error():
    assert common.final_status(16, "other error\nDONE (ERROR, rc=16)", 1) == "error"


def test_portfolio_pass_is_not_replaced_by_a_failed_abc_engine():
    text = ("engine_0: abc bmc3\nengine_0: Error: Does not work for combinational networks.\n"
            "engine_1: Status returned by engine: pass\nDONE (PASS, rc=0)")
    assert common.final_status(0, text, 1) == "pass"
