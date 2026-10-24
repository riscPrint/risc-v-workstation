"""Invalid X filters are input errors through the CLI and MCP."""
import pytest

from rvw.cli import main
from rvw.mcp.registry import Registry


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / "top.sv"
    source.write_text("module top(input clk, output y); assign y = 0; endmodule\n")
    out = tmp_path / "out"
    out.mkdir()
    (out / "result.json").write_text('{"status":"pass"}\n')
    return source, out


def test_invalid_filter_cli(inputs, capsys):
    source, out = inputs
    with pytest.raises(SystemExit) as exc:
        main(["formal", "xprop", "--verilog", str(source), "--top", "top",
              "--outputs", "--filter", "[", "--out", str(out)])
    assert exc.value.code == 2
    assert "--filter '['" in capsys.readouterr().err
    assert not (out / "result.json").exists()
    assert not (out / "module_ports.ys").exists()


def test_invalid_filter_mcp(inputs):
    source, out = inputs
    registry, problems = Registry.discover({"formal"})
    assert not problems
    try:
        _, started, error = registry.call_json("formal_xprop", {
            "verilog": [str(source)], "top": "top", "out": str(out),
            "outputs": True, "filter": "[",
        })
        assert not error, error
        _, status, error = registry.call_json("job_status", {"job_id": started["job_id"], "wait_s": 30})
        assert not error, error
        assert status["status"] == "failed", status
        assert "exit 2" in status["error"], status
        assert "--filter '['" in "\n".join(status["log_tail"]), status
        assert not (out / "result.json").exists()
    finally:
        registry.jobs.shutdown()
