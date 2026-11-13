from rvw.mcp.envelope import envelope
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

import pytest

from rvw.cli import main
from rvw.mcp.registry import Registry
from rvw.query.db import SCHEMA, DesignDB
from rvw.query.diff import diff
from rvw.query.mcp_tools import mcp_tools


def copy_db(source, dest):
    with sqlite3.connect(source) as src, sqlite3.connect(dest) as dst:
        src.backup(dst)
    return dest


def parity(old, new, capsys, *, scope=None, connections=True):
    args = ["query", "diff", str(old), str(new), "--json"]
    params = {"old": str(old), "new": str(new), "connections": connections}
    if scope:
        args += ["--scope", scope]
        params["scope"] = scope
    if not connections:
        args.append("--no-connections")
    assert main(args) == 0
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", params)
    assert not error and envelope(cli) == json.loads(text)
    return cli


@pytest.mark.parametrize("connections", [False, True])
@pytest.mark.parametrize("scope", [None, "_zz_y"])
def test_generated_port_attributes_cli_mcp(probe_db, capsys, connections, scope):
    old, new = [probe_db("r19_port_init" + str(n)) for n in (0, 1)]
    with closing(DesignDB(old)) as db:
        assert db.q("SELECT generated, direction FROM signals WHERE path='_zz_y'") == [(1, "out")]
    result = parity(old, new, capsys, scope=scope, connections=connections)
    assert result["summary"]["identical"] is False
    assert result["ports"]["changed"][0]["path"] == "_zz_y"
    assert "tags" in result["ports"]["changed"][0]["changes"]
    assert parity(old, old, capsys, scope=scope, connections=connections)["summary"]["identical"] is True


@pytest.mark.parametrize("connections", [False, True])
@pytest.mark.parametrize("scope", [None, "_zz_y"])
def test_generated_port_incomplete_cli_mcp(probe_db, capsys, connections, scope):
    database = probe_db("r19_port_unknown")
    result = parity(database, database, capsys, scope=scope, connections=connections)
    assert result["summary"]["identical"] is None
    assert "_zz_y" in result["undetermined"]["paths"]


@pytest.mark.parametrize("direction", ["in", "out", "inout"])
@pytest.mark.parametrize("field,value", [("width", 2), ("type", "Bits"), ("tags", "attribute:init=1")])
def test_generated_port_declarations(gcd_db, tmp_path, direction, field, value):
    old = copy_db(gcd_db, tmp_path / "old.db")
    new = tmp_path / "new.db"
    with sqlite3.connect(old) as db:
        db.execute("UPDATE signals SET generated=1, direction=? WHERE path='y'", (direction,))
    copy_db(old, new)
    with sqlite3.connect(new) as db:
        db.execute(f"UPDATE signals SET {field}=? WHERE path='y'", (value,))
    with closing(DesignDB(old)) as a, closing(DesignDB(new)) as b:
        result = diff(a, b, scope="y", connections=False)
    assert result["summary"]["identical"] is False
    assert field in result["ports"]["changed"][0]["changes"]


@pytest.mark.parametrize("kind", ["wire", "reg"])
@pytest.mark.parametrize("pruned", [False, True])
@pytest.mark.parametrize("location", ["tags", "type", "clock", "assignment", "condition"])
def test_hidden_generated_incomplete_keys(gcd_db, tmp_path, kind, pruned, location):
    database = copy_db(gcd_db, tmp_path / "hidden.db")
    with sqlite3.connect(database) as db:
        sid, cd = db.execute("SELECT id, clock_domain_id FROM signals WHERE path='y'").fetchone()
        db.execute("UPDATE signals SET generated=1, direction=NULL, port_index=NULL, kind=?, pruned=? WHERE id=?",
                   (kind, pruned, sid))
        marker = "$incomplete:round19"
        if location in ("tags", "type"):
            db.execute(f"UPDATE signals SET {location}=? WHERE id=?", (marker, sid))
        elif location == "clock":
            assert cd is not None
            db.execute("UPDATE clock_domains SET clock_key=? WHERE id=?", (marker, cd))
        elif location == "assignment":
            db.execute("UPDATE assignments SET key=? WHERE target_id=?", (marker, sid))
        else:
            db.execute("UPDATE conds SET key=? WHERE id IN (SELECT cond_id FROM assignments WHERE target_id=?)",
                       (marker, sid))
            assert db.execute("SELECT count(*) FROM conds WHERE key=?", (marker,)).fetchone()[0]
    with closing(DesignDB(database)) as db:
        result = diff(db, db, connections=False)
    assert result["summary"]["identical"] is None
    assert "y" in result["undetermined"]["paths"]


def test_readme_current_schema_contract():
    readme = (Path(__file__).resolve().parents[2] / "SpinalDB/README.md").read_text()
    version = int(SCHEMA.rsplit("/", 1)[1])
    assert f"### Schema `{SCHEMA}`" in readme
    match = re.search(r"Navigation reads schemas `/1` through `/(\d+)`\. "
                      r"Diff requires `/(\d+)` on both sides\.", readme)
    assert match is not None
    assert tuple(map(int, match.groups())) == (version, version)


def test_platform_contracts_current_schema_contract():
    c6 = (Path(__file__).resolve().parents[2] / 'docs/contracts/c6-design-database.md').read_text()
    version = int(SCHEMA.rsplit('/', 1)[1])
    match = re.search(r'`rvw query diff` requires `/(\d+)` and refuses `/(\d+)` and older files', c6)
    assert match is not None
    assert tuple(map(int, match.groups())) == (version, version - 1)
