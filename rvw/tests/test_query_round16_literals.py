from rvw.mcp.envelope import envelope
import json
from contextlib import closing

from rvw.cli import main
from rvw.mcp.registry import Registry
from rvw.query.db import DesignDB
from rvw.query.diff import diff
from rvw.query.mcp_tools import mcp_tools


def test_unknown_spinal_package_literal_cannot_prove_identical(probe_db):
    with closing(DesignDB(probe_db("r16_literal0"))) as a, closing(DesignDB(probe_db("r16_literal1"))) as b:
        result = diff(a, b)
        assert result["summary"]["identical"] is None
        assert result["undetermined"]


def test_untrusted_literal_diff_cli_mcp_parity(probe_db, capsys):
    a, b = (str(probe_db(f"r16_literal{n}")) for n in (0, 1))
    assert main(["query", "diff", a, b, "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": a, "new": b})
    assert not error
    assert envelope(cli) == json.loads(text)
    assert cli["summary"]["identical"] is None
