from rvw.mcp.envelope import envelope
import json
from contextlib import closing

import pytest

from rvw.cli import main
from rvw.mcp.registry import Registry
from rvw.query import ops
from rvw.query.db import DesignDB
from rvw.query.mcp_tools import mcp_tools


@pytest.fixture
def probe(probe_db):
    return probe_db


def test_clock_role_keeps_data_dependencies(probe):
    with closing(DesignDB(probe("r16_clockdata"))) as db:
        assert db.resolve_one("gclk").clock_role == "clock"
        assert ops.path(db, "io_a", "io_y", data_only=True)["found"]
        assert {"path": "gclk", "kinds": ["data"], "signal_kind": "wire"} in ops.loads(db, "io_a")["readers"]
        assert "gclk" in {s["path"] for s in ops.drivers(db, "io_y")["read_signals"]}
        assert "gclk" in {s["path"] for s in ops.fanin(db, "io_y")["nodes"]}
        assert "io_y" in {s["path"] for s in ops.fanout(db, "io_a", depth=2)["nodes"]}
        # A clock-domain relation alone does not give a data path to the register.
        assert not ops.path(db, "io_a", "logic_r")["found"]
        assert not ops.path(db, "io_a", "io_z")["found"]


@pytest.mark.parametrize("role", ["clock", "reset", "clock_enable", "soft_reset"])
def test_generated_control_signals_keep_data_paths(probe, tmp_path, role):
    import sqlite3

    path = tmp_path / "control.db"
    with sqlite3.connect(probe("r16_clockdata")) as src, sqlite3.connect(path) as dst:
        src.backup(dst)
        dst.execute("UPDATE signals SET generated = 1, clock_role = ? WHERE path = 'gclk'", (role,))
    with closing(DesignDB(path)) as db:
        result = ops.path(db, "io_a", "io_y", data_only=True)
        assert result["found"]
        assert [h["path"] for h in result["paths"][0]["hops"]] == ["io_a", "io_y"]


@pytest.mark.parametrize("role", ["clock", "reset", "clock_enable", "soft_reset"])
def test_clock_filter_uses_edge_kind_before_collapsing(probe, tmp_path, role):
    import sqlite3

    path = tmp_path / "relation.db"
    with sqlite3.connect(probe("r16_clockdata")) as src, sqlite3.connect(path) as dst:
        src.backup(dst)
        # Synthetic relation: schema /14 stores domain controls in clock_domains, not edges.
        dst.execute("UPDATE signals SET generated = 1 WHERE path = 'gclk'")
        dst.execute("INSERT INTO edges SELECT a.id, b.id, ? FROM signals a, signals b "
                    "WHERE a.path = 'gclk' AND b.path = 'logic_r'", (role,))
    with closing(DesignDB(path)) as db:
        assert not ops.path(db, "io_a", "logic_r")["found"]
        assert "io_y" in {s["path"] for s in ops.fanout(db, "io_a", depth=2)["nodes"]}
        assert "logic_r" not in {s["path"] for s in ops.fanout(db, "io_a", depth=2)["nodes"]}
        assert "logic_r" in {s["path"] for s in ops.fanout(db, "io_a", depth=2, include_clock=True)["nodes"]}
        assert "io_a" not in {s["path"] for s in ops.fanin(db, "logic_r", depth=2)["nodes"]}
        assert "io_a" in {s["path"] for s in ops.fanin(db, "logic_r", depth=2, include_clock=True)["nodes"]}


@pytest.mark.parametrize("operation,args,tool,kwargs", [
    ("path", ["io_a", "io_y"], "query_path", {"a": "io_a", "b": "io_y"}),
    ("drivers", ["io_y"], "query_drivers", {"signal": "io_y"}),
    ("loads", ["io_a"], "query_loads", {"signal": "io_a"}),
    ("fanin", ["io_y"], "query_fanin", {"signal": "io_y"}),
    ("fanout", ["io_a"], "query_fanout", {"signal": "io_a"}),
])
def test_clock_data_cli_mcp_parity(probe, capsys, operation, args, tool, kwargs):
    db = str(probe("r16_clockdata"))
    assert main(["query", operation, *args, "--db", db, "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json(tool, {"db": db, **kwargs})
    assert not error
    assert envelope(cli) == json.loads(text)
