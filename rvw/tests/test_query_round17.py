from contextlib import closing
import json
import sqlite3

import pytest

from rvw.cli import main
from rvw.mcp.registry import Registry
from rvw.query import diff as diff_mod, ops
from rvw.query.db import DesignDB, QueryError
from rvw.query.mcp_tools import mcp_tools


def test_diff_unknown_scope_cli_mcp(gcd_db, capsys):
    with closing(DesignDB(gcd_db)) as db:
        with pytest.raises(QueryError, match="no diff scope"):
            diff_mod.diff(db, db, scope="typo")
    assert main(["query", "diff", str(gcd_db), str(gcd_db), "--scope", "typo", "--json"]) == 2
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {
        "old": str(gcd_db), "new": str(gcd_db), "scope": "typo"})
    assert error
    assert cli == json.loads(text)


@pytest.mark.parametrize("reverse", [False, True])
def test_diff_scope_present_on_one_side(gcd_db, tmp_path, reverse):
    dest = tmp_path / "removed.db"
    with sqlite3.connect(gcd_db) as src, sqlite3.connect(dest) as dst:
        src.backup(dst)
        dst.execute("UPDATE signals SET path = 'removed_y' WHERE path = 'y'")
    with closing(DesignDB(gcd_db)) as a, closing(DesignDB(dest)) as b:
        result = diff_mod.diff(b, a, scope="y") if reverse else diff_mod.diff(a, b, scope="y")
    assert result["summary"]["identical"] is False
    assert result["signals"]["counts"]["added" if reverse else "removed"] == 1


@pytest.mark.parametrize("operation,args", [
    (ops.hierarchy, ("typo",)), (ops.component, ("typo",)), (ops.regs, ("typo",)),
    (ops.where, ("typo",)), (ops.drivers, ("typo",)), (ops.loads, ("typo",)),
    (ops.fanin, ("typo",)), (ops.fanout, ("typo",)), (ops.path, ("typo", "y")),
])
def test_query_unknown_paths_refuse(gcd_db, operation, args):
    with closing(DesignDB(gcd_db)) as db, pytest.raises(QueryError):
        operation(db, *args)


def test_search_scope_applies_to_components(cluster_db):
    with closing(DesignDB(cluster_db)) as db:
        with pytest.raises(QueryError):
            ops.search(db, "*", scope="typo")
        result = ops.search(db, "*", scope="units_1", kind="component")
        assert result["total"] == 1
        assert result["matches"][0]["component"] == "units_1"


@pytest.mark.parametrize("kind", ["named", "gen"])
def test_signal_subclass_diff_is_undetermined(probe_db, kind, capsys):
    old, new = (probe_db(f"r17_reset{mode}_{kind}") for mode in (0, 1))
    with closing(DesignDB(old)) as a, closing(DesignDB(new)) as b:
        result = diff_mod.diff(a, b)
        assert result["summary"]["identical"] is None
        assert result["undetermined"]["count"] > 0
        assert diff_mod.diff(a, a)["summary"]["identical"] is None
    assert main(["query", "diff", str(old), str(new), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": str(old), "new": str(new)})
    assert not error
    assert cli == json.loads(text)
    assert cli["summary"]["identical"] is None


def test_blackbox_clock_role_paths_drivers_loads(probe_db, capsys):
    path = probe_db("r17_clockbox")
    with closing(DesignDB(path)) as db:
        assert db.resolve_one("bb.c").clock_role == "clock"
        assert ops.path(db, "clk", "y")["found"]
        assert "bb.c" in {r["path"] for r in ops.drivers(db, "bb.y")["read_signals"]}
        assert "bb.y" in {r["path"] for r in ops.loads(db, "bb.c")["readers"]}
        assert "bb.c" in {r["path"] for r in ops.fanin(db, "bb.y")["nodes"]}
        assert "bb.y" in {r["path"] for r in ops.fanout(db, "bb.c")["nodes"]}
    assert main(["query", "path", "clk", "y", "--db", str(path), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_path", {"db": str(path), "a": "clk", "b": "y"})
    assert not error
    assert cli == json.loads(text)
    assert cli["found"]


@pytest.mark.parametrize("old_side", [False, True])
def test_diff_schema15_refused_cli_mcp(gcd_db, tmp_path, capsys, old_side):
    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(gcd_db) as src, sqlite3.connect(legacy) as dst:
        src.backup(dst)
        dst.execute("UPDATE meta SET value='rvw.designdb/15' WHERE key='schema'")
    old, new = (legacy, gcd_db) if old_side else (gcd_db, legacy)
    assert main(["query", "diff", str(old), str(new), "--json"]) == 2
    cli = json.loads(capsys.readouterr().out)
    assert "diff needs rvw.designdb/20" in cli["error"]
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": str(old), "new": str(new)})
    assert error
    assert cli == json.loads(text)


@pytest.mark.parametrize("name", ["r17_unused0"])
def test_unread_generated_declaration_is_undetermined(probe_db, name):
    with closing(DesignDB(probe_db(name))) as db:
        assert diff_mod.diff(db, db)["summary"]["identical"] is None


def test_generated_only_scope_refuses(probe_db):
    with closing(DesignDB(probe_db("r17_reset0_gen"))) as db:
        with pytest.raises(QueryError, match="no comparable objects"):
            diff_mod.diff(db, db, scope="_zz_custom")
