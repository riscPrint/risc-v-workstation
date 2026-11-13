import json
import pytest
from rvw.cli import main

pytestmark = pytest.mark.fast

@pytest.mark.parametrize("case", ["missing", "schema", "clock_binding"])
def test_invalid_autocheck_is_structured_error(tmp_path, capsys, case):
    manifest = tmp_path / "plan.json"
    if case == "schema":
        manifest.write_text('{"schema":"invalid"}')
    elif case == "clock_binding":
        manifest.write_text(json.dumps({"schema":"rvw.autocheck/1", "top":"Core",
            "clock":"clk", "reset":"reset", "verilog":[],
            "ports":{"valid":{"direction":"output", "width":1}}}))
    assert main(["formal", "autocheck", str(manifest), "--out", str(tmp_path / "out"), "--json"]) == 2
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "error" and result["error"]
    assert "Traceback" not in output.err
    assert not (tmp_path / "out/result.json").exists()
