from rvw.mcp.envelope import envelope
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time

import pytest

from rvw.cli import main
from rvw.common.proc import run_group
from rvw.mcp.registry import Registry
from rvw.query import diff as diff_mod, ops
from rvw.query.db import DesignDB
from rvw.query.mcp_tools import mcp_tools


SYNC = ["sync_dont", "sync_read", "enabled_dont", "enabled_read",
        "rw_dont", "rw_read", "rw_write", "rw_during_do", "rw_during_dont"]


def parity(capsys, database, operation, args, cli_args):
    assert main(["query", operation, *cli_args, "--db", str(database), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_" + operation, {"db": str(database), **args})
    assert not error
    assert envelope(cli) == json.loads(text)
    return cli


@pytest.mark.parametrize("name", SYNC)
def test_sync_read_state_cli_mcp(probe_db, capsys, name):
    database = probe_db("r18_" + name)
    sources = ["addr"]
    if name.startswith(("enabled", "rw")):
        sources.append("en")
    if name.startswith("rw"):
        sources.extend(["wen", "data", "mask"])
    for source in sources:
        args = {"a": source, "b": "y"}
        result = parity(capsys, database, "path", args, [source, "y"])
        assert result["found"]
        assert {p["register_stages"] for p in result["paths"]} == {1}
        assert all(any(h["kind"] == "mem_read" for h in p["hops"]) for p in result["paths"])
        assert not parity(capsys, database, "path", {**args, "comb_only": True},
                          [source, "y", "--comb-only"])["found"]
    with closing(DesignDB(database)) as db:
        assert ops.path(db, "mem", "y")["paths"][0]["register_stages"] == 1
        assert not ops.path(db, "mem", "y", comb_only=True)["found"]
        assert not ops.path(db, "addr", "y", data_only=True)["found"]
        direct = ops.path(db, "data", "direct", comb_only=True)
        assert direct["found"] and direct["paths"][0]["register_stages"] == 0
        state = db.q("SELECT path FROM signals WHERE kind='mem_read'")[0][0]
        info = ops.where(db, state)["signal"]
        assert info["clock_domain"]["clock"] == "clk"
        assert "wave" not in info and "verilog" not in info
        assert "database node" in ops.drivers(db, state)["origin"]
        assert any(p.get("output") == state for p in ops.drivers(db, "mem")["memory"]["ports"])
    fanin = parity(capsys, database, "fanin", {"signal": "y", "depth": 20, "stop_at_regs": True},
                   ["y", "--depth", "20", "--stop-at-regs"])
    assert any(n["kind"] == "mem_read" for n in fanin["nodes"])
    assert "addr" not in {n["path"] for n in fanin["nodes"]}
    fanout = parity(capsys, database, "fanout", {"signal": "addr", "depth": 20, "stop_at_regs": True},
                    ["addr", "--depth", "20", "--stop-at-regs"])
    assert "y" not in {n["path"] for n in fanout["nodes"]}


def test_async_read_stays_combinational(probe_db, capsys):
    database = probe_db("r18_async_dont")
    result = parity(capsys, database, "path", {"a": "addr", "b": "y", "comb_only": True},
                    ["addr", "y", "--comb-only"])
    assert result["found"] and result["paths"][0]["register_stages"] == 0


def test_simulation_only_include_diff_cli_mcp(probe_db, capsys):
    old, new = [probe_db("r18_box" + str(i)) for i in (0, 1)]
    with closing(DesignDB(old)) as a, closing(DesignDB(new)) as b:
        assert a.q("SELECT body_sha256 FROM blackboxes")[0][0]
        assert diff_mod.diff(a, a)["summary"]["identical"] is True
        assert diff_mod.diff(a, b)["summary"]["identical"] is False
    assert main(["query", "diff", str(old), str(new), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": str(old), "new": str(new)})
    assert not error and envelope(cli) == json.loads(text)
    assert cli["summary"]["identical"] is False


def test_unknown_preprocessor_context_is_undetermined(probe_db, capsys):
    database = probe_db("r18_box_unknown")
    assert main(["query", "diff", str(database), str(database), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": str(database), "new": str(database)})
    assert not error and envelope(result) == json.loads(text)
    assert result["summary"]["identical"] is None
    with closing(DesignDB(database)) as db:
        body, key = db.q("SELECT body_sha256, key FROM blackboxes")[0]
        assert body is None and "$incomplete:" in key and "OUTSIDE" in key


@pytest.mark.parametrize("old_side", [False, True])
def test_schema16_diff_refused(gcd_db, tmp_path, capsys, old_side):
    database = tmp_path / "schema16.db"
    with sqlite3.connect(gcd_db) as src, sqlite3.connect(database) as dst:
        src.backup(dst)
        dst.execute("UPDATE meta SET value='rvw.designdb/16' WHERE key='schema'")
    old, new = (database, gcd_db) if old_side else (gcd_db, database)
    assert main(["query", "diff", str(old), str(new), "--json"]) == 2
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": str(old), "new": str(new)})
    assert error and envelope(cli) == json.loads(text)
    assert "diff needs rvw.designdb/20" in cli["error"]


def test_legacy_sync_graph_refuses(cluster_db, tmp_path, capsys):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(cluster_db) as src, sqlite3.connect(database) as dst:
        src.backup(dst)
        dst.execute("UPDATE meta SET value='rvw.designdb/16' WHERE key='schema'")
        dst.execute("ALTER TABLE mem_ports DROP COLUMN output_id")
    assert main(["query", "path", "io_rdAddr", "io_rsp_payload", "--db", str(database), "--json"]) == 2
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_path", {
        "db": str(database), "a": "io_rdAddr", "b": "io_rsp_payload"})
    assert error and envelope(cli) == json.loads(text)
    assert "synchronous memory dependency queries need rvw.designdb/17" in cli["error"]


@pytest.mark.parametrize("cancel", [False, True])
def test_hdl_scan_stops_descendants(tmp_path, cancel):
    runner = Path(__file__).resolve().parents[2] / "SpinalDB/scripts/hdl-deps.py"
    pid = tmp_path / "pid"
    tool = tmp_path / "yosys"
    tool.write_text(f'#!{sys.executable}\n'
                    'import os,pathlib,subprocess,sys,time\n'
                    'if "--version" in sys.argv: print("test yosys"); sys.exit(0)\n'
                    'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])\n'
                    f'pathlib.Path({str(pid)!r}).write_text(str(os.getppid())+","+str(p.pid))\n'
                    'time.sleep(60)\n')
    tool.chmod(0o700)
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    request.write_text(json.dumps({"requests": [{"top": "Box", "files": [],
        "inline": [["verilog", "module Box; endmodule"]], "params": [],
        "yosys": str(tool), "timeout": 60 if cancel else 0.5}]}))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_group, [sys.executable, str(runner), "--scan", str(request), str(output)], timeout=15, capture=True)
        if cancel:
            deadline = time.monotonic() + 10
            while not pid.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert pid.exists(), "scan child did not start"
            parent, child = map(int, pid.read_text().split(","))
            os.kill(parent, signal.SIGTERM)
        result = future.result(timeout=20)
    if cancel:
        assert result.returncode == 130
    else:
        assert result.returncode == 0
        (scan,) = json.loads(output.read_text())["results"]
        assert scan["chunks"] == [] and "exit 124" in scan["problems"][0]
    child = int(pid.read_text().split(",")[1])
    from test_proc import _alive
    deadline = time.monotonic() + 5
    while _alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(child), "scan descendant is still running"
