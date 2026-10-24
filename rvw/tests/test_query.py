import gzip
import json
import re
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.query import cli as query_cli
from rvw.query import diff as diff_mod
from rvw.query import ops
from rvw.query.db import DesignDB, QueryError
from rvw.query.diff import _Snapshot as _Snap


@pytest.fixture()
def gcd(gcd_db):
    d = DesignDB(gcd_db)
    yield d
    d.close()


@pytest.fixture()
def cluster(cluster_db):
    d = DesignDB(cluster_db)
    yield d
    d.close()


# ------------------------------------------------------------------------------------------- names
@pytest.mark.parametrize("name", [
    "fifo.logic_ptr_push",                       # RTL path
    "TOP.GcdCluster.fifo.logic_ptr_push",        # waveform path
    "TOP/GcdCluster/fifo/logic_ptr_push[2:0]",   # Surfer style with a bit range
    "GcdCluster.fifo.logic_ptr_push",            # toplevel module first
    "fifo.logic.ptr.push",                       # Spinal path through Areas
    "StreamFifo.logic_ptr_push",                 # module.name of a single-instance module
    "logic_ptr_push",                            # unique Verilog name
    "fifo.logic.ptr_push",                       # mixed Spinal/Verilog
])
def test_resolve_forms(cluster, name):
    assert cluster.resolve_one(name).path == "fifo.logic_ptr_push"


def test_resolve_vec_and_bundle_fields(cluster):
    assert cluster.resolve_one("io.cmd.payload(1)").path == "io_cmd_payload_1"
    assert cluster.resolve_one("io_cmd_payload[1]").path == "io_cmd_payload_1"
    assert cluster.resolve_one("fifo.io.push.payload.0").path == "fifo.io_push_payload_0"


def test_resolve_dedup_suffix(cluster):
    # `units.0.x`-style: instance segment without Spinal's `_<n>` suffix is ambiguous, with it unique
    assert cluster.resolve_one("units_1.x").path == "units_1.x"


def test_ambiguous_lists_candidates(cluster):
    with pytest.raises(QueryError) as e:
        cluster.resolve_one("x")
    assert {"units_0.x", "units_1.x"} <= set(e.value.candidates)


def test_group_and_unknown(cluster):
    with pytest.raises(QueryError, match="group"):
        cluster.resolve_one("io.cmd")
    assert len(cluster.resolve("io.cmd", allow_group=True)) == 4
    with pytest.raises(QueryError, match="no signal"):
        cluster.resolve_one("nope_not_here")


def test_component_names(cluster):
    assert cluster.resolve_component("TOP.GcdCluster.fifo")["module"] == "StreamFifo"
    assert cluster.resolve_component("units_1")["path"] == "units_1"
    with pytest.raises(QueryError) as e:   # `units` matches units_0 and units_1 (Spinal dedup suffix)
        cluster.resolve_component("units")
    assert set(e.value.candidates) == {"units_0", "units_1"}


def test_pruned_is_explained(gcd):
    with pytest.raises(QueryError, match="pruned"):
        gcd.resolve_one("tmp")


# ------------------------------------------------------------------------------------------- queries
def test_where(cluster):
    w = ops.where(cluster, "fifo.logic.ptr.push")["signal"]
    assert w["verilog"] == {"module": "StreamFifo", "name": "logic_ptr_push"}
    assert w["wave"] == "TOP.GcdCluster.fifo.logic_ptr_push"
    assert w["area"] == "logic.ptr"
    assert w["reset_value"] == "0" and w["clock_domain"]["reset_kind"] == "ASYNC"
    assert w["loc"].endswith("Demo.scala:43")
    g = ops.where(cluster, "io.cmd")
    assert g["bundle"]["type"] == "Stream" and g["count"] == 4


def test_drivers_register_with_conditions(gcd):
    d = ops.drivers(gcd, "x")
    assert d["signal"]["kind"] == "reg"
    assert d["register"]["reset"] is None and "not reset" in d["register"]["note"]
    srcs = [(a["source"], a.get("condition")) for a in d["assignments"]]
    assert srcs == [("x - y", "when(y < x)"), ("io_a", "when(io_loadValues)")]
    assert all(a["loc"].endswith(".scala:%d" % n) for a, n in zip(d["assignments"], (20, 26)))
    assert {r["path"] for r in d["read_signals"]} == {"x", "y", "io_a", "io_loadValues"}


def test_drivers_reset_and_else(cluster):
    d = ops.drivers(cluster, "units_0.x")
    assert d["register"]["reset"] == {"signal": "reset", "kind": "ASYNC", "active": "high", "value": "0"}
    conds = [a.get("condition") for a in d["assignments"]]
    assert conds == ["when(io_load)", "!(io_load) && when(y < x)"]


def test_drivers_memory_and_primary_input(cluster):
    m = ops.drivers(cluster, "fifo.logic_ram")
    assert m["memory"]["depth"] == 4 and m["memory"]["width"] == 32
    assert {p["kind"] for p in m["memory"]["ports"]} == {"write", "read_sync"}
    assert m["assignments"][0]["kind"] == "mem_write" and m["assignments"][0]["enable"]
    assert ops.drivers(cluster, "io_rdAddr")["origin"] == "primary input of the toplevel"


def test_loads(gcd):
    r = ops.loads(gcd, "x")
    readers = {x["path"]: x["kinds"] for x in r["readers"]}
    assert readers["io_result"] == ["data"]
    assert readers["x"] == ["data", "cond"]  # x := x - y under when(y < x)
    assert readers["y"] == ["data", "cond"]


def test_fanin_fanout(cluster):
    fi = ops.fanin(cluster, "io_rsp_payload", depth=3)
    assert [(n["path"], n["depth"]) for n in fi["nodes"][:3]] == [
        ("results_sum", 1), ("units_0.io_result", 2), ("units_1.io_result", 2)]
    assert {"units_0.x", "units_1.x"} <= set(fi["registers"])
    fo = ops.fanout(cluster, "io.cmd", depth=1)   # an interface
    assert fo["start"] and any(n["path"].startswith("fifo.io_push") for n in fo["nodes"])
    stop = ops.fanin(cluster, "io_rsp_payload", depth=10, stop_at_regs=True)
    full = ops.fanin(cluster, "io_rsp_payload", depth=10)
    assert len(full["nodes"]) > len(stop["nodes"])


def test_path(gcd):
    p = ops.path(gcd, "io_a", "io_result")
    assert p["found"]
    hops = [h["path"] for h in p["paths"][0]["hops"]]
    assert hops == ["io_a", "x", "io_result"]
    assert p["paths"][0]["register_stages"] == 1
    assert p["paths"][0]["hops"][1]["logic"][0]["source"] == "io_a"
    assert not ops.path(gcd, "io_a", "io_result", comb_only=True)["found"]


def test_path_through_hierarchy(cluster):
    p = ops.path(cluster, "io.cmd", "io_rsp_payload", data_only=True)
    assert p["found"]
    comps = {h["path"].split(".")[0] for h in p["paths"][0]["hops"]}
    assert "fifo" in comps


def test_search(cluster):
    assert {m["path"] for m in ops.search(cluster, "ptr*push", kind="reg")["matches"]} == {"fifo.logic_ptr_push"}
    assert ops.search(cluster, r"units_\d\.x$", regex=True)["total"] == 2
    comps = ops.search(cluster, "StreamFifo", kind="component")["matches"]
    assert comps == [{"component": "fifo", "module": "StreamFifo", "class": "StreamFifo"}]
    assert ops.search(cluster, "x", scope="units_1", kind="reg")["total"] == 1


def test_hierarchy_component_regs(cluster):
    h = ops.hierarchy(cluster)
    assert {c["name"] for c in h["root"]["children"]} == {"fifo", "units_0", "units_1"}
    c = ops.component(cluster, "fifo")
    assert {"interface": "io.push", "type": "Stream"}.items() <= next(i for i in c["interfaces"] if i["interface"] == "io.push").items()
    assert c["memories"][0]["name"] == "logic_ram"
    assert {a["area"] for a in c["areas"]} >= {"logic.ptr", "logic.pop.sync"}
    top = ops.regs(cluster, None, recursive=True)
    assert {"units_0.x", "units_1.y", "fifo.logic_ptr_pop"} <= {r["path"] for r in top["registers"]}
    assert ops.regs(cluster, "units_0")["count"] == 2


def test_info_and_export(cluster, tmp_path):
    i = ops.info(cluster)
    assert i["meta"]["schema"] == "rvw.designdb/20" and i["counts"]["components"] == 4
    assert {a["name"] for a in i["artifacts"]} == {"blocks.json", "pdg.json", "hgldd/GcdCluster.dd"}
    b = ops.export(cluster, "blocks", str(tmp_path / "b.json"))
    assert json.loads((tmp_path / "b.json").read_text())["format"] == "spinalblocks" and b["bytes"] > 0
    ops.export(cluster, "pdg", str(tmp_path / "pdg.json.gz"))
    assert "vertices" in json.loads(gzip.decompress((tmp_path / "pdg.json.gz").read_bytes()))
    ops.export(cluster, "hgldd", str(tmp_path / "h.dd"))
    assert "HGLDD" in json.loads((tmp_path / "h.dd").read_text())


# ------------------------------------------------------------------------------------------- diff
def test_diff_identical(gcd_db):
    a, b = DesignDB(gcd_db), DesignDB(gcd_db)
    assert diff_mod.diff(a, b)["summary"]["identical"]


def test_diff_logic_change(gcd_db, buggy_db):
    r = diff_mod.diff(DesignDB(gcd_db), DesignDB(buggy_db))
    assert not r["summary"]["identical"]
    changed = {c["path"]: c for c in r["assignments"]["changed"]}
    assert set(changed) == {"x"}
    assert any("x - y" in o for o in changed["x"]["old"]) and any("(x - y) - 1" in n for n in changed["x"]["new"])
    assert r["ports"]["counts"] == {"added": 0, "removed": 0, "changed": 0}


def test_diff_structure(gcd_db, cluster_db):
    r = diff_mod.diff(DesignDB(gcd_db), DesignDB(cluster_db))
    assert r["summary"]["components"]["added"] == 3
    assert any(p["path"] == "io_cmd_valid" for p in r["ports"]["added"])
    assert r["connections"]["counts"]["added"] > 0


# ------------------------------------------------------------------------------------------- CLI
def test_cli_json(cluster_db, capsys):
    assert main(["query", "drivers", "--db", str(cluster_db), "--json", "units_1.y"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["signal"]["path"] == "units_1.y"


def test_cli_text_and_errors(cluster_db, capsys, monkeypatch):
    monkeypatch.setenv("RVW_DESIGNDB", str(cluster_db))
    assert main(["query", "path", "io_cmd_payload_0", "io_rsp_payload"]) == 0
    assert "register stages" in capsys.readouterr().out
    assert main(["query", "where", "x"]) == 2
    assert "ambiguous" in capsys.readouterr().err
    assert main(["query", "where", "--json", "x"]) == 2
    assert "candidates" in json.loads(capsys.readouterr().out)


def test_cli_diff(gcd_db, buggy_db, capsys):
    assert main(["query", "diff", str(gcd_db), str(buggy_db)]) == 0
    assert "~ logic of x" in capsys.readouterr().out


# ------------------------------------------------------------------------------- review regressions
def _copy_db(src, dst, *sql):
    import shutil
    import sqlite3
    shutil.copy(src, dst)
    con = sqlite3.connect(dst)
    for s in sql:
        con.execute(s)
    con.commit()
    con.close()
    return dst


@pytest.mark.parametrize("reverse", [False, True])
def test_diff_sees_first_or_last_driver(gcd_db, tmp_path, reverse):
    # An inout may have no driver. Compare assignment targets even if only one side has a driver.
    undriven = _copy_db(gcd_db, tmp_path / "undriven.db",
                        "DELETE FROM assignments WHERE target_id = (SELECT id FROM signals WHERE path = 'io_result')")
    a, b = DesignDB(gcd_db), DesignDB(undriven)
    try:
        result = diff_mod.diff(b, a, connections=False) if reverse else diff_mod.diff(a, b, connections=False)
        assert result["summary"]["identical"] is False
        change = next(c for c in result["assignments"]["changed"] if c["path"] == "io_result")
        assert bool(change["old"]) is not reverse
        assert bool(change["new"]) is reverse
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("kind", ["analog", "literal", "mask", "meminit", "poison"])
def test_diff_round15_emitted_hardware_and_cli_mcp(probe, kind, capsys):
    from rvw.mcp.registry import Registry
    from rvw.query.mcp_tools import mcp_tools

    paths = [probe(f"r15_{kind}{n}") for n in (0, 1)]
    a, b = map(DesignDB, paths)
    try:
        result = diff_mod.diff(a, b)
        assert result["summary"]["identical"] is not True
        assert diff_mod.diff(b, a)["summary"]["identical"] is not True
        if kind == "analog":
            assert result["assignments"]["changed"][0]["old"] == []
            assert result["assignments"]["changed"][0]["new"]
        elif kind == "poison":
            assert result["summary"]["identical"] is False
            assert result["emission_config"]["changed"]
            assert diff_mod.diff(a, b, scope=a.top, connections=False)["summary"]["identical"] is False
        else:
            assert result["summary"]["identical"] is None
            assert result["undetermined"]["count"] > 0
        assert main(["query", "diff", *map(str, paths), "--json"]) == 0
        cli_result = json.loads(capsys.readouterr().out)
        text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": str(paths[0]), "new": str(paths[1])})
        assert not error
        assert cli_result == json.loads(text) == result
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("config", [None, "$incomplete:emission config custom phase"])
def test_diff_missing_or_unmodelled_emission_config_is_undetermined(gcd_db, tmp_path, config):
    sql = ("DELETE FROM meta WHERE key = 'emission_config'" if config is None else
           f"UPDATE meta SET value = '{config}' WHERE key = 'emission_config'")
    path = _copy_db(gcd_db, tmp_path / "config.db", sql)
    db = DesignDB(path)
    try:
        result = diff_mod.diff(db, db, scope="x")
        assert result["summary"]["identical"] is None
        assert "<emission_config>" in result["undetermined"]["paths"]
    finally:
        db.close()


def test_same_path_is_ambiguous_not_first_row(cluster_db, tmp_path):
    # BOOM small: `...regNext.br_mask` is the Spinal path of `..._br_mask` and `..._br_mask_1`;
    # the first row used to hide the second.
    db = _copy_db(cluster_db, tmp_path / "dup.db",
                  "UPDATE signals SET spinal_path = 'units.shared' WHERE path IN ('units_0.x', 'units_1.x')")
    d = DesignDB(db)
    try:
        with pytest.raises(QueryError) as e:
            d.resolve_one("units.shared")
        assert e.value.candidates == ["units_0.x", "units_1.x"]
        assert {s.path for s in d.resolve("units.shared", allow_group=True)} == {"units_0.x", "units_1.x"}
        with pytest.raises(QueryError):  # through the CLI-facing operations too
            ops.drivers(d, "units.shared")
    finally:
        d.close()


def test_named_signal_does_not_win_over_generated_twins(cluster_db, tmp_path):
    # BOOM small: `_zz_4` names 20 signals, one not flagged generated; it was picked silently.
    db = _copy_db(cluster_db, tmp_path / "zz.db",
                  "UPDATE signals SET generated = 0 WHERE path = 'units_0.when_Demo_l21'")
    d = DesignDB(db)
    try:
        with pytest.raises(QueryError) as e:
            d.resolve_one("when_Demo_l21")
        assert set(e.value.candidates) == {"units_0.when_Demo_l21", "units_1.when_Demo_l21"}
    finally:
        d.close()


def test_path_to_itself_finds_feedback_loops(cluster):
    # Review finding: `path rob_head rob_head` (rob_head -> next_rob_head -> rob_head) found nothing.
    r = ops.path(cluster, "ctrl_fsm_stateReg", "ctrl_fsm_stateReg")
    assert r["found"]
    assert [h["path"] for h in r["paths"][0]["hops"]] == ["ctrl_fsm_stateReg", "ctrl_fsm_stateNext", "ctrl_fsm_stateReg"]
    assert r["paths"][0]["register_stages"] == 1
    self_loop = ops.path(cluster, "units_0.x", "units_0.x")  # x := x - y
    assert self_loop["found"] and self_loop["paths"][0]["length"] == 1


def test_stale_database_warns(gcd_db, tmp_path, capsys):
    # Review finding: `rvw query` answered from a database built at another revision without a word.
    import subprocess
    repo = tmp_path / "core"
    git = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@x", *a],  # noqa: E731
                                    check=True, capture_output=True, text=True).stdout.strip()
    repo.mkdir()
    git("init", "-q")
    (repo / "Core.scala").write_text("class Core\n")
    git("add", ".")
    git("commit", "-qm", "one")
    built = git("rev-parse", "--short", "HEAD")
    db = _copy_db(gcd_db, tmp_path / "stale.db",
                  f"INSERT INTO meta VALUES ('core_repo', '{repo}')", f"INSERT INTO meta VALUES ('core_rev', '{built}')",
                  "INSERT INTO meta VALUES ('core_dirty', 'false')")
    d = DesignDB(db)
    assert d.staleness() == []
    (repo / "Core.scala").write_text("class Core2\n")
    assert any("uncommitted" in w for w in d.staleness())
    git("commit", "-qam", "two")
    assert any("older than the sources" in w for w in d.staleness())
    d.close()
    assert main(["query", "where", "x", "--db", str(db), "--json"]) == 0
    out = capsys.readouterr()
    assert "older than the sources" in out.err
    assert any("older than the sources" in w for w in json.loads(out.out)["db_warnings"])
    from rvw.query import mcp_tools
    handler = next(t for t in mcp_tools.mcp_tools() if t.name == "query_where").handler
    assert any("older than the sources" in w for w in handler(db=str(db), signal="x")["db_warnings"])


# ------------------------------------------------------------------------------- build-db.sh
FAKE_SBT = """#!{python}
import json, os, sys
from pathlib import Path
cmd = sys.argv[-1]
args = []
if "--args-file" in cmd:
    raw = Path(cmd.split("--args-file ", 1)[1]).read_bytes().decode()
    args = raw.split("\\0")[:-1]
lock_dir = os.environ.get("RVW_LOCK_DIR")
Path(os.environ["FAKE_SBT_LOG"]).write_text(json.dumps({{
    "argv": sys.argv[1:], "cwd": os.getcwd(), "args": args, "spinal_boom": os.environ.get("SPINAL_BOOM"),
    "locks": sorted(os.listdir(lock_dir)) if lock_dir and os.path.isdir(lock_dir) else [],
    "held": os.environ.get("RVW_LOCKS_HELD", "")}}))
"""


def _fake_sbt(tmp_path, monkeypatch):
    import os
    import sys
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sbt = bin_dir / "sbt"
    sbt.write_text(FAKE_SBT.format(python=sys.executable))
    sbt.chmod(0o755)
    log = tmp_path / "sbt.json"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_SBT_LOG", str(log))
    monkeypatch.setenv("RVW_LOCK_DIR", str(tmp_path / "locks"))
    return log


def test_build_db_passes_paths_with_spaces_and_semicolons(tmp_path, monkeypatch):
    # Review finding: `sbt "runMain ... $out ${rest[*]}"` split paths with spaces and let `;` chain
    # another sbt command.
    import subprocess
    from rvw.query.mcp_tools import repo_root
    log = _fake_sbt(tmp_path, monkeypatch)
    out = tmp_path / "space dir" / "a;b.db"
    subprocess.run([str(repo_root() / "SpinalDB/build-db.sh"), "class", "my.Top", str(out), "--test",
                    "--meta", "note=x y; publishLocal", "--source-root", str(tmp_path / "src dir")], check=True)
    r = json.loads(log.read_text())
    assert r["argv"][-1].startswith("Test/runMain spinaldb.Main --args-file /")
    assert " " not in r["argv"][-1].split("--args-file ", 1)[1] and ";" not in r["argv"][-1]
    assert r["args"] == ["my.Top", str(out), "--meta", "note=x y; publishLocal", "--source-root", str(tmp_path / "src dir")]


def test_build_db_named_entry_takes_its_settings_from_entry_sh(tmp_path, monkeypatch):
    import subprocess
    from rvw.query.mcp_tools import repo_root
    log = _fake_sbt(tmp_path, monkeypatch)
    monkeypatch.setenv("SPINAL_BOOM", str(tmp_path / "core"))
    out = tmp_path / "o u t.db"
    subprocess.run([str(repo_root() / "SpinalDB/build-db.sh"), "boom", "small", str(out), "--no-pdg"], check=True)
    r = json.loads(log.read_text())
    assert r["cwd"] == str(repo_root() / "SpinalDB/boom")
    assert r["args"] == ["small", str(out), "--no-pdg"] and r["argv"][-1].startswith("run --args-file /")
    # sbt runs while holding the machine-wide `boom` lock (shared re-entry variable, C7/Resources)
    assert r["spinal_boom"] == str(tmp_path / "core") and "boom" in [e.split(":")[0] for e in r["held"].split(",") if e]
    bad = subprocess.run([str(repo_root() / "SpinalDB/build-db.sh"), "../x", "small", str(out)], capture_output=True)
    assert bad.returncode == 2


def test_build_db_tool_is_generic(monkeypatch):
    # Review finding: query_build_db had a `boom_config` argument in generic code.
    from rvw.mcp.spec import ToolError
    from rvw.query import mcp_tools
    spec = next(t for t in mcp_tools.mcp_tools() if t.name == "query_build_db")
    props = spec.input_schema["properties"]
    assert "boom_config" not in props and {"entry", "config"} <= set(props)
    assert "boom" in mcp_tools.entries()
    with pytest.raises(ToolError, match="unknown entry"):
        mcp_tools._build_db("x.db", entry="nope", config="small")
    with pytest.raises(ToolError, match="needs `config`"):
        mcp_tools._build_db("x.db", entry="boom")


def test_cov_heavy_lock_is_configurable(monkeypatch):
    from rvw.cov import mcp_tools
    monkeypatch.delenv("RVW_HEAVY_LOCK", raising=False)
    assert mcp_tools.heavy_lock() == mcp_tools.DEFAULT_HEAVY_LOCK
    monkeypatch.setenv("RVW_HEAVY_LOCK", "fpga")
    assert mcp_tools.heavy_lock() == "fpga"
    monkeypatch.setenv("RVW_HEAVY_LOCK", "")
    assert mcp_tools.heavy_lock() is None
    assert mcp_tools.heavy_lock("mine") == "mine"
    specs = {t.name: t for t in mcp_tools.mcp_tools()}
    assert "lock" in specs["cov_prove"].input_schema["properties"]


# ------------------------------------------------------------------------------- typed diff, masks
@pytest.fixture()
def probe(probe_db):
    return probe_db


def test_diff_sees_signed_vs_unsigned_shift(probe):
    # Review finding: `(io.a.asSInt >> 3)` and `(io.a >> 3)` both render `io_a >> 3`; diff said identical.
    a, b = DesignDB(probe("cast_unsigned")), DesignDB(probe("cast_signed"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (c,) = [c for c in r["assignments"]["changed"] if c["path"] == "io_y"]
        assert c["old"] == c["new"] and "typed" in c["note"] and c["old_keys"] != c["new_keys"]
        assert diff_mod.diff(a, a)["summary"]["identical"]
    finally:
        a.close()
        b.close()


def test_diff_sees_changed_rom_contents(probe):
    a, b = DesignDB(probe("rom1")), DesignDB(probe("rom2"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        assert r["memories"]["changed"][0]["path"] == "rom" and "init_sha256" in r["memories"]["changed"][0]["changes"]
        assert ops.drivers(a, "rom")["memory"]["init"]["words"] == 4
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("schema", ["rvw.designdb/1", "rvw.designdb/2", "rvw.designdb/3", "rvw.designdb/4",
                                    "rvw.designdb/5", "rvw.designdb/6", "rvw.designdb/7", "rvw.designdb/8",
                                    "rvw.designdb/9", "rvw.designdb/10", "rvw.designdb/11",
                                    "rvw.designdb/12", "rvw.designdb/13", "rvw.designdb/14", "rvw.designdb/15", "rvw.designdb/16", "rvw.designdb/17", "rvw.designdb/18"])
def test_diff_refuses_older_schemas(gcd_db, tmp_path, schema):
    # /2 wrote `$gen:<type>` for multi-driver temporaries: a diff could call a changed mux identical.
    # /3 had no clock-enable/soft-reset polarity and wrote generated registers as `$gen:<type>`.
    # /4 expanded generated registers only four deep: a deeper operand swap could diff as identical.
    # /5 had no clock-domain control keys and gave equal-content registers one id.
    # /6 had no memory-port policies or BlackBox generics in its keys and ignored unmodelled constructs.
    # /7 keyed enums by encoding name only and did not hash the files a BlackBox body includes.
    # /8 keyed a switch default without the case keys and generated registers without their tags.
    # /9 masked user signals named like `when_X_l12`, keyed object tags by class and had no port order.
    # /10 wrote strings in keys unescaped, assertion kinds by identity hash, and did not key attribute
    # subclasses or `$`-named object fields.
    # /11 sorted tags and attributes and left out user fields named `bitmap$0` or `serialVersionUID`.
    # /12 read a case-class tag through `productIterator`, which the class can override.
    # /14 trusted library class names without checking class identity, loader and code source.
    old = _copy_db(gcd_db, tmp_path / "old.db", f"UPDATE meta SET value = '{schema}' WHERE key = 'schema'",
                   *(["ALTER TABLE clock_domains DROP COLUMN clock_enable_active_high",
                      "ALTER TABLE clock_domains DROP COLUMN soft_reset_active_high"]
                     if schema not in ("rvw.designdb/1", "rvw.designdb/4", "rvw.designdb/5", "rvw.designdb/6",
                                       "rvw.designdb/7", "rvw.designdb/8", "rvw.designdb/9", "rvw.designdb/10",
                                       "rvw.designdb/11", "rvw.designdb/12", "rvw.designdb/13", "rvw.designdb/14", "rvw.designdb/15", "rvw.designdb/16", "rvw.designdb/17", "rvw.designdb/18")
                     else []))
    a, b = DesignDB(old), DesignDB(gcd_db)
    try:
        assert ops.info(a)["meta"]["schema"] == schema  # still readable for queries
        assert ops.drivers(a, "x")["register"]["clock"] == "clk"  # clock domains without polarity columns
        for old_db, new_db in ((a, b), (b, a)):
            with pytest.raises(QueryError, match="diff needs rvw.designdb/20.*Rebuild the database"):
                diff_mod.diff(old_db, new_db)
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("old_side", [True, False])
def test_diff_refuses_schema14_cli_mcp(gcd_db, tmp_path, capsys, old_side):
    from rvw.mcp.registry import Registry
    from rvw.query.mcp_tools import mcp_tools

    old = _copy_db(gcd_db, tmp_path / "old.db",
                   "UPDATE meta SET value = 'rvw.designdb/14' WHERE key = 'schema'")
    a, b = (old, gcd_db) if old_side else (gcd_db, old)
    assert main(["query", "diff", str(a), str(b), "--json"]) == 2
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json("query_diff", {"old": str(a), "new": str(b)})
    assert error
    assert json.loads(text) == cli
    assert "diff needs rvw.designdb/20" in cli["error"]
    assert "Rebuild the database" in cli["error"]
    assert "summary" not in cli


def _counts_zero(r, *cats):
    return all(not any(r["summary"][c].values()) if c != "connections" else
               not (r["summary"][c]["added"] or r["summary"][c]["removed"]) for c in cats)


def test_diff_sees_changed_mux_constant(probe):
    # Round-2 finding: `io.sel.mux(1 -> U(2))` vs `U(3)`: the mux result is a temporary with three
    # drivers; the Verilog differs but diff said identical.
    a, b = DesignDB(probe("mux2")), DesignDB(probe("mux3"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (c,) = r["assignments"]["changed"]
        assert c["path"] == "io_y" and c["old_keys"] != c["new_keys"]
        assert any(":= 2 when switch(io_sel) is(1)" in t for t in c["old_temporaries"])
        assert any(":= 3 when switch(io_sel) is(1)" in t for t in c["new_temporaries"])
        assert "  + (temporary) " in query_cli.render("diff", r)
        assert diff_mod.diff(a, DesignDB(probe("mux2")))["summary"]["identical"]
    finally:
        a.close()
        b.close()


def test_diff_line_shift_is_not_a_logic_change(probe):
    # Round-2 finding: one added blank line renamed `when_File_l31` -> `l32`: signals, connections and
    # logic all showed as changed. Only the (test-only) class name differs here.
    a, b, c = DesignDB(probe("shift_a")), DesignDB(probe("shift_b")), DesignDB(probe("shift_c"))
    try:
        r = diff_mod.diff(a, b)
        assert _counts_zero(r, "signals", "ports", "registers", "memories", "assignments", "connections"), r["summary"]
        assert [x["changes"] for x in r["components"]["changed"]] == [{"class": {"old": "ShiftA", "new": "ShiftB"}}]
        r = diff_mod.diff(a, c)  # `>` -> `>=` in the when condition: a real change
        assert [x["path"] for x in r["assignments"]["changed"]] == ["r"]
    finally:
        for d in (a, b, c):
            d.close()


def test_diff_never_masks_names_in_keys(probe, tmp_path):
    # Round 11 (/tmp/review11-a/extra/named-cli.json): diff masked `when_X_l<N>` in every key, so two
    # real signals named like line names diffed as one. SpinalDB never writes a temporary's name into a
    # key (it is expanded by content), so a name in a key is a real signal: never masked.
    def shifted(n):
        return _copy_db(probe("shift_a"), tmp_path / f"s{n}.db",
                        f"UPDATE assignments SET key = key || ' w when_Shift_l{n}:Bool'")
    a, b = DesignDB(shifted(31)), DesignDB(shifted(32))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"] and r["summary"]["assignments"]["changed"] > 0, r["summary"]
    finally:
        a.close()
        b.close()


def test_diff_sees_user_registers_named_like_line_names(probe):
    # Round 11 (/tmp/review11-a/Named.scala): registers the user named `when_Test_l12` / `_l13`;
    # `io.y := first - second` vs `second - first` diffed identical (both keys masked to `_l*`).
    a, b = DesignDB(probe("named_regs0")), DesignDB(probe("named_regs1"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        assert [c["path"] for c in r["assignments"]["changed"]] == ["io_y"]
        # The user's registers and wire are named signals, not hidden temporaries.
        assert {"when_Test_l12", "when_Test_l13", "when_Test_l14"} <= set(_Snap(a, None).signals)
        assert diff_mod.diff(a, DesignDB(probe("named_regs0")))["summary"]["identical"]
    finally:
        a.close()
        b.close()


def test_diff_never_masks_assertion_messages(probe):
    # Round 11 (/tmp/review11-a/extra/assertion-diff.json): message "when_Test_l12" vs "_l13" was masked.
    a, b = DesignDB(probe("assert_msg0")), DesignDB(probe("assert_msg1"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (c,) = r["components"]["changed"]
        old, new = c["changes"]["statements"]["old"], c["changes"]["statements"]["new"]
        assert '"when_Test_l12"' in old[0]["key"] and '"when_Test_l13"' in new[0]["key"]
    finally:
        a.close()
        b.close()


def test_diff_sees_port_order(probe):
    # Round 11 (/tmp/review11-a/extra/ports-cli.json): module ports (a, b, io_y) vs (b, a, io_y) diffed
    # identical: the port order was not stored.
    a, b = DesignDB(probe("port_order0")), DesignDB(probe("port_order1"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (c,) = r["components"]["changed"]
        assert c["changes"]["ports"] == {"old": [["a", "in", "Bool", 1], ["b", "in", "Bool", 1], ["io_y", "out", "Bool", 1]],
                                         "new": [["b", "in", "Bool", 1], ["a", "in", "Bool", 1], ["io_y", "out", "Bool", 1]]}
        assert r["ports"]["reordered"] == ["<top>"]
        assert "~ port order of <top>" in query_cli.render("diff", r)
        assert diff_mod.diff(a, DesignDB(probe("port_order0")))["summary"]["identical"]
    finally:
        a.close()
        b.close()


def test_diff_sees_object_tag_payload(probe):
    # Round 11 (/tmp/review11-a/extra/objtag-diff.json): `object Payload extends SpinalTag { var value }`
    # with value 0 vs 1 was keyed by its class name only.
    a, b = DesignDB(probe("obj_tag0")), DesignDB(probe("obj_tag1"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (c,) = r["signals"]["changed"]
        assert c["path"] == "io_y" and "value=Int(0)" in c["changes"]["tags"]["old"] and \
            "value=Int(1)" in c["changes"]["tags"]["new"]
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("pair,table", [("r12_seq", "signals"), ("r12_assert", "components"), ("r12_lang", "signals")])
def test_diff_sees_escaped_strings_and_attribute_subclasses(probe, pair, table):
    # Round 12 (/tmp/review12-a/More2.scala, MemAttr.scala): `SeqTag(Vector("a\",\"b"))` vs
    # `Vector("a","b")`, an assertion message `"hi\",io_a:Bool,\""` vs `"hi", io.a, ""`, and an
    # `AttributeFlag` subclass emitted in Verilog vs in no language, all diffed identical.
    a, b = DesignDB(probe(pair + "0")), DesignDB(probe(pair + "1"))
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is False and r["undetermined"]["count"] == 0, r["summary"]
        assert r[table]["changed"], r
        assert diff_mod.diff(a, DesignDB(probe(pair + "0")))["summary"]["identical"] is True
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("pair,path,old,new", [
    ("r13_order", "r", '"init"=Int(0)', '"init"=Int(1)'),
    ("r13_bitmap", "io_y", "bitmap$0=Int(0)", "bitmap$0=Int(1)"),
    ("r13_serial", "io_y", "serialVersionUID=Long(0)", "serialVersionUID=Long(1)"),
])
def test_diff_sees_attribute_order_and_user_fields_named_like_compiler_ones(probe, pair, path, old, new):
    # Round 13 (/tmp/review13-a/Attack.scala): attributes `init` 0 then 1 vs 1 then 0 (the netlist
    # takes the last one) had one sorted key, and an object tag's user field named `bitmap$0` or
    # `serialVersionUID` was left out by name: all three pairs diffed identical.
    a, b = DesignDB(probe(pair + "0")), DesignDB(probe(pair + "1"))
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is False and r["undetermined"]["count"] == 0, r["summary"]
        changed = [c for t in ("signals", "registers") for c in r[t]["changed"] if c["path"] == path]
        assert changed and changed[0]["changes"]["tags"]["old"] != changed[0]["changes"]["tags"]["new"], r
        tags_old, tags_new = changed[0]["changes"]["tags"]["old"], changed[0]["changes"]["tags"]["new"]
        # The first value written is the first one listed (attributes keep the emitted order).
        assert tags_old.index(old) < tags_old.index(new) if pair == "r13_order" else (old in tags_old and new in tags_new)
        if pair == "r13_order":
            assert tags_new.index(new) < tags_new.index(old)
        assert diff_mod.diff(a, DesignDB(probe(pair + "0")))["summary"]["identical"] is True
    finally:
        a.close()
        b.close()


def test_diff_sees_case_class_fields_hidden_by_product_iterator(probe):
    # Round 14 (/tmp/review14-a/Attack14.scala): `case class R14Hidden(x: Int)` overrides
    # `productIterator` to return `0`; /12 read the tag through it, so `R14Hidden(0)` and
    # `R14Hidden(1)` had one key and diffed `identical: true`. /13 reads the fields by reflection.
    a, b = DesignDB(probe("r14_hidden0")), DesignDB(probe("r14_hidden1"))
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is False and r["undetermined"]["count"] == 0, r["summary"]
        changed = [c for c in r["signals"]["changed"] if c["path"] == "io_y"]
        assert changed, r
        tags = changed[0]["changes"]["tags"]
        assert "x=Int(0)" in tags["old"] and "x=Int(1)" in tags["new"], tags
        for n in ("r14_hidden0", "r14_hidden1"):
            assert diff_mod.diff(a if n.endswith("0") else b, DesignDB(probe(n)))["summary"]["identical"] is True
    finally:
        a.close()
        b.close()


# Old composite strings of the `domain_rise` / `assert_msg0` fixtures: the domain display and the
# control keys, as diff.py joined them before it compared structured values.
_OLD_DOMAIN = "clk RISING, reset reset ASYNC active-high"
_OLD_DOMAIN_KEYS = "clock clk:Bool; reset reset:Bool"


@pytest.mark.parametrize("fixture,sql", [
    # Domain keys were joined `role key; role key`: a clock key holding `; reset reset:Bool` and no
    # reset key read like the clock key and the reset key.
    ("domain_rise", "UPDATE clock_domains SET clock_key = 'clk:Bool; reset reset:Bool', reset_key = NULL"),
    # Memory-port fields were joined with `, `: a port key ending in the clock field, with no clock
    # domain, read like the key plus the port's real clock domain.
    ("domain_rise", "UPDATE mem_ports SET clock_domain_id = NULL, key = key || ', clock " + _OLD_DOMAIN +
     " {" + _OLD_DOMAIN_KEYS + "}' WHERE kind = 'write'"),
    # A statement was `kind key clock D {keys}`: a key ending in that text, with no clock domain, read
    # like the key in its clock domain.
    ("assert_msg0", "UPDATE statements SET clock_domain_id = NULL, key = key || ' clock " + _OLD_DOMAIN +
     " {" + _OLD_DOMAIN_KEYS + "}'"),
])
def test_diff_compares_structured_parts_never_joined_strings(probe, tmp_path, fixture, sql):
    # Coordinator follow-up to round 12: two different part lists that joined to one string diffed
    # as identical. Every combined comparison value is now a list or dict of its parts.
    src = probe(fixture)
    a, b = DesignDB(src), DesignDB(_copy_db(src, tmp_path / "joined.db", sql))
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is False, r["summary"]
        assert diff_mod.diff(a, DesignDB(probe(fixture)))["summary"]["identical"] is True
    finally:
        a.close()
        b.close()


_IDENTITY = re.compile(r"[\w$]@[0-9a-f]{1,8}(?![\w$])")
_KEY_COLUMNS = [("assignments", "key"), ("conds", "key"), ("mem_ports", "key"), ("statements", "key"),
                ("memories", "key"), ("signals", "tags"), ("signals", "type"), ("components", "tags"), ("blackboxes", "key"),
                ("clock_domains", "reset_kind"), ("clock_domains", "clock_edge"), ("clock_domains", "clock_key"),
                ("clock_domains", "reset_key"), ("clock_domains", "clock_enable_key"), ("clock_domains", "soft_reset_key")]


@pytest.mark.parametrize("name", sorted(p.stem for p in (Path(__file__).parent / "data").glob("*.sql")))
def test_fixture_keys_hold_no_identity_hash(probe, name):
    # Round 12 (/tmp/review12-a/More2.scala Determinism): an assertion key held
    # `AssertStatementKind@1b2c3d`, which changes between runs. No key may hold an identity hash.
    d = DesignDB(probe(name))
    try:
        assert d.schema == "rvw.designdb/20"
        for table, col in _KEY_COLUMNS:
            for (v,) in d.q(f"SELECT {col} FROM {table}"):
                assert v is None or not _IDENTITY.search(v), f"{name} {table}.{col}: {v}"
    finally:
        d.close()


def test_memory_write_mask_is_a_dependency(probe):
    # Review finding: loads(io_mask) was empty and `path io_mask mem` found nothing.
    d = DesignDB(probe("masked"))
    try:
        loads = ops.loads(d, "io_mask")
        assert [r["path"] for r in loads["readers"]] == ["mem"] and loads["readers"][0]["kinds"] == ["cond"]
        assert loads["statements"][0]["mask"] == "io_mask"
        assert ops.path(d, "io_mask", "mem")["found"] and ops.path(d, "io_mask", "io_y")["found"]
        assert any(a.get("mask") == "io_mask" for a in ops.drivers(d, "mem")["assignments"])
    finally:
        d.close()


def test_diff_sees_reset_value_of_generated_register(probe):
    # Round-4 finding (/tmp/review4-design/diff-generated.json): `RegNext(io.a + 1) init k` is a
    # generated register; k 1 -> 2 changed the Verilog but diff said identical.
    a, b = DesignDB(probe("gen_init1")), DesignDB(probe("gen_init2"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (c,) = [c for c in r["assignments"]["changed"] if c["path"] == "io_y"]
        assert c["old"] == c["new"] and c["old_keys"] != c["new_keys"]
        assert any(g["register"]["reset_value"] == "1" and "UIntLiteral[8]=1" in diff_mod._enc(g) for g in c["old_generated"])
        assert any(g["register"]["reset_value"] == "2" and "UIntLiteral[8]=2" in diff_mod._enc(g) for g in c["new_generated"])
        assert "(generated register)" in query_cli.render("diff", r)
        assert diff_mod.diff(a, DesignDB(probe("gen_init1")))["summary"]["identical"]
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("other, field", [("domain_fall", "FALLING"), ("domain_sync", "SYNC"),
                                          ("domain_low", "active-low")])
def test_diff_sees_clock_domain_controls(probe, other, field):
    # Round-4 finding (/tmp/review4-design/db/diff-high-fall.json): the diff reduced each clock domain
    # to its clock name, so a register and a memory write port moved to the falling edge (or to a
    # synchronous or active-low reset on the same signal) diffed as identical.
    a, b = DesignDB(probe("domain_rise")), DesignDB(probe("domain_" + other.split("_")[1]))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (reg,) = r["registers"]["changed"]
        assert reg["path"] == "area_r" and field in reg["changes"]["clock_domain"]["new"].values()
        assert reg["changes"]["clock_domain"]["old"] == {"clock": "clk", "edge": "RISING", "reset": "reset",
                                                         "reset_kind": "ASYNC", "reset_polarity": "active-high"}
        (mem,) = r["memories"]["changed"]
        assert mem["path"] == "area_mem" and any(field in p["clock"].values() for p in mem["changes"]["ports"]["new"])
        assert diff_mod.diff(a, DesignDB(probe("domain_rise")))["summary"]["identical"]
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("control, field", [("enable", "enable"), ("soft", "soft_reset")])
def test_diff_sees_enable_and_soft_reset_polarity(probe, control, field):
    # Round-5 finding (/tmp/review5-b/enable_high-diff.json, soft_high-diff.json): the clock domain
    # did not store clockEnableActiveLevel / softResetActiveLevel; flipping one diffed as identical.
    a, b = DesignDB(probe(f"{control}_high")), DesignDB(probe(f"{control}_low"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (reg,) = r["registers"]["changed"]
        change = reg["changes"]["clock_domain"]
        assert reg["path"] == "area_r" and change["old"][field] == change["new"][field] == "io_en"
        assert change["old"][f"{field}_polarity"] == "active-high" and change["new"][f"{field}_polarity"] == "active-low"
        assert ops.drivers(b, "area_r")["register"]["clock"] == "clk"
        assert b.clock_domain(b.resolve_one("area_r").clock_domain_id)[
            "clock_enable_active" if control == "enable" else "soft_reset_active"] == "low"
        assert diff_mod.diff(a, DesignDB(probe(f"{control}_high")))["summary"]["identical"]
    finally:
        a.close()
        b.close()


def test_diff_keeps_operand_position_of_generated_registers(probe):
    # Round-5 finding (/tmp/review5-b/expr-swap-True.json): `a - b` vs `b - a` of two unnamed
    # `RegNext` registers gave identical keys (`$gen:<type>` twice plus a sorted set of registers).
    a, b = DesignDB(probe("swap_a")), DesignDB(probe("swap_b"))
    try:
        r = diff_mod.diff(a, b)
        assert not r["summary"]["identical"]
        (c,) = [c for c in r["assignments"]["changed"] if c["path"] == "io_y"]
        assert c["old_keys"] != c["new_keys"]
        assert diff_mod.diff(a, DesignDB(probe("swap_a")))["summary"]["identical"]
    finally:
        a.close()
        b.close()


def test_diff_keeps_operand_position_below_four_registers(probe):
    # Round-6 finding (/tmp/review6/deepgen5-diff.json): `a - b` vs `b - a` of two five-stage
    # `RegNext` chains was `identical: true`; the /4 key stopped four registers deep.
    a, b = DesignDB(probe("deep_a")), DesignDB(probe("deep_b"))
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is False and r["summary"]["undetermined"] == 0
        (c,) = [c for c in r["assignments"]["changed"] if c["path"] == "io_y"]
        assert c["old_keys"] != c["new_keys"] and "incomplete" not in c
        same = diff_mod.diff(a, DesignDB(probe("deep_a")))
        assert same["summary"]["identical"] is True and same["undetermined"]["count"] == 0
    finally:
        a.close()
        b.close()


def test_diff_with_incomplete_keys_is_never_identical(probe, tmp_path, capsys):
    # A key SpinalDB could not make complete (`$incomplete:`, or a hashed part `h!:`) cannot show two
    # designs equal: the diff is undetermined (`identical: null`), with the paths listed.
    src = probe("deep_a")
    key = "UPDATE assignments SET key = '{}' WHERE target_id = (SELECT id FROM signals WHERE path = 'io_y')"
    for marker in ("$incomplete:UInt[8]", "h!:0123456789abcdef0123456789abcdef"):
        old = _copy_db(src, tmp_path / "old.db", key.format(f"Sub({marker},{marker})"))
        new = _copy_db(src, tmp_path / "new.db", key.format(f"Sub({marker},{marker})"))
        a, b = DesignDB(old), DesignDB(new)
        try:
            r = diff_mod.diff(a, b)
            assert r["summary"]["identical"] is None and r["summary"]["undetermined"] == 1, r["summary"]
            assert r["undetermined"]["paths"] == ["io_y"] and r["undetermined"]["reason"]
            # Only one side incomplete: still undetermined. A real change elsewhere: not identical.
            r = diff_mod.diff(a, DesignDB(src))
            assert r["summary"]["identical"] is not True
            r = diff_mod.diff(a, DesignDB(probe("deep_b")))
            assert r["summary"]["identical"] is False
        finally:
            a.close()
            b.close()
    assert main(["query", "diff", str(tmp_path / "old.db"), str(tmp_path / "new.db")]) == 0
    assert "? undetermined" in capsys.readouterr().out


def test_diff_sees_changed_clock_enable_logic(probe):
    # Round-7 finding (/tmp/review7/enablelogic-diff.json): `clockEnable = io.a > 1` vs `> 2` is a
    # generated wire with the same name: the domain row was equal and the diff `identical: true`.
    a, b = DesignDB(probe("enable_logic1")), DesignDB(probe("enable_logic2"))
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is False, r["summary"]
        (c,) = [c for c in r["registers"]["changed"] if c["path"] == "area_r"]
        assert set(c["changes"]) == {"clock_domain_logic"}
        old, new = c["changes"]["clock_domain_logic"]["old"], c["changes"]["clock_domain_logic"]["new"]
        assert [r for r, _ in old] == ["clock", "reset", "enable"] and "io_a" in old[2][1] and old != new
        same = diff_mod.diff(a, DesignDB(probe("enable_logic1")))
        assert same["summary"]["identical"] is True and same["undetermined"]["count"] == 0
    finally:
        a.close()
        b.close()


def test_diff_keeps_distinct_generated_registers_distinct(probe):
    # Round-7 finding (/tmp/review7/probes/sharing0-sharing1-diff.json): two generated registers with
    # equal drivers had one content id, so `(r - r) - s` vs `(r - s) - s` was `identical: true`.
    a, b = DesignDB(probe("sharing0")), DesignDB(probe("sharing1"))
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is False and r["summary"]["undetermined"] == 0
        (c,) = [c for c in r["assignments"]["changed"] if c["path"] == "io_y"]
        assert c["old_keys"] != c["new_keys"]
        assert diff_mod.diff(a, DesignDB(probe("sharing0")))["summary"]["identical"] is True
    finally:
        a.close()
        b.close()


def test_diff_with_incomplete_clock_domain_key_is_undetermined(probe, tmp_path):
    # An incomplete control key cannot show two domains equal: registers there are undetermined.
    src = probe("enable_logic1")
    sql = "UPDATE clock_domains SET clock_enable_key = '$incomplete:Bool' WHERE clock_enable IS NOT NULL"
    old, new = _copy_db(src, tmp_path / "o.db", sql), _copy_db(src, tmp_path / "n.db", sql)
    a, b = DesignDB(old), DesignDB(new)
    try:
        r = diff_mod.diff(a, b)
        assert r["summary"]["identical"] is None and "area_r" in r["undetermined"]["paths"], r["summary"]
    finally:
        a.close()
        b.close()


# --------------------------------------------------------------------- round 8: allow-list rule
def _diff(probe, old, new):
    a, b = DesignDB(probe(old)), DesignDB(probe(new))
    try:
        return diff_mod.diff(a, b)
    finally:
        a.close()
        b.close()


def test_diff_sees_memory_port_read_under_write(probe):
    # Round-8 finding (/tmp/review8/rw-cli.json): readWriteSync with readFirst vs writeFirst was
    # `identical: true`; the port key now holds every port setting.
    r = _diff(probe, "rw0", "rw1")
    assert r["summary"]["identical"] is False and r["summary"]["undetermined"] == 0, r["summary"]
    (m,) = r["memories"]["changed"]
    old, new = m["changes"]["ports"]["old"], m["changes"]["ports"]["new"]
    assert "rw=readFirst" in old[0]["key"] and "rw=writeFirst" in new[0]["key"] and "dw=doRead" in old[0]["key"]
    assert _diff(probe, "rw0", "rw0")["summary"]["identical"] is True


def test_diff_sees_blackbox_generics_and_needs_its_body(probe):
    # Round-8 finding (/tmp/review8/bb-cli.json): a BlackBox generic K=1 vs K=2 was `identical: true`.
    r = _diff(probe, "box1", "box2")
    assert r["summary"]["identical"] is False, r["summary"]
    (c,) = [c for c in r["components"]["changed"] if c["path"] == "b"]
    assert "K=Int 1" in c["changes"]["blackbox"]["old"] and "K=Int 2" in c["changes"]["blackbox"]["new"]
    # Without its external body the BlackBox cannot be shown equal, not even to itself ...
    same = _diff(probe, "box1", "box1")
    assert same["summary"]["identical"] is None and same["undetermined"]["paths"] == ["b"], same["summary"]
    # ... with the body supplied (--blackbox-source) it can.
    assert _diff(probe, "box1_src", "box1_src")["summary"]["identical"] is True
    assert _diff(probe, "box1_src", "box2_src")["summary"]["identical"] is False


def test_diff_with_an_unmodelled_construct_is_undetermined(probe, tmp_path):
    # Allow-list rule: SaltedNot (a test-defined node class with its own parameter) is not modelled.
    # Two designs that differ only in that parameter have equal keys; the diff must not say identical.
    # The two test designs are separate Scala classes (`SaltedNot1`, `SaltedNot2`): give both the same
    # class name, so the salt is the only difference left.
    sql = "UPDATE components SET class_name = 'spinaldb.UnsupportedDesign', module = 'UnsupportedDesign'"
    one, two = _copy_db(probe("salted_not1"), tmp_path / "one.db", sql), _copy_db(probe("salted_not2"), tmp_path / "two.db", sql)
    a, b = DesignDB(one), DesignDB(two)
    try:
        r = diff_mod.diff(a, b)
    finally:
        a.close()
        b.close()
    assert r["summary"]["identical"] is None and r["undetermined"]["paths"] == ["io_y"], r["summary"]
    assert "do not model" in r["undetermined"]["reason"]
    assert _diff(probe, "salted_not1", "salted_not1")["summary"]["identical"] is None
    assert _diff(probe, "plain_not", "salted_not1")["summary"]["identical"] is not True
    assert _diff(probe, "plain_not", "plain_not")["summary"]["identical"] is True


def test_diff_and_drivers_tell_initial_from_init(probe, capsys):
    # `init` (reset value) and `initial` (power-on value) were one kind: the diff said identical.
    r = _diff(probe, "init_reg", "initial_reg")
    assert r["summary"]["identical"] is False, r["summary"]
    assert main(["query", "drivers", "r", "--db", str(probe("initial_reg"))]) == 0
    assert "initial := 5" in capsys.readouterr().out


# --------------------------------------------------------------------- round 9: complete definitions
def test_diff_sees_enum_order_and_encoded_values(probe, tmp_path):
    # Round-9 finding (/tmp/review9/adversarial enum, reorder): enum keys named the encoding only, so
    # a changed custom encoding and reordered elements were `identical: true`.
    for old, new, before, after in (("enum_custom0", "enum_custom1", "{a=0,b=1,c=2}", "{a=1,b=2,c=0}"),
                                    ("enum_order0", "enum_order1", "{a=0,b=1,c=2}", "{b=0,a=1,c=2}")):
        r = _diff(probe, old, new)
        assert r["summary"]["identical"] is False and r["summary"]["undetermined"] == 0, (old, r["summary"])
        (s,) = [c for c in r["signals"]["changed"] if c["path"] == "state_1"]
        assert s["changes"]["type"]["old"].endswith(before) and s["changes"]["type"]["new"].endswith(after), s
        assert _diff(probe, old, old)["summary"]["identical"] is True
    # An enum whose values SpinalDB could not evaluate cannot be shown equal, not even to itself.
    broken = _copy_db(probe("enum_custom0"), tmp_path / "broken.db",
                      "UPDATE signals SET type = '$incomplete:enum State@custom' WHERE path = 'state_1'")
    a = DesignDB(broken)
    try:
        r = diff_mod.diff(a, a)
    finally:
        a.close()
    assert r["summary"]["identical"] is None and "state_1" in r["undetermined"]["paths"], r["summary"]


def test_diff_sees_a_header_the_blackbox_body_includes(probe):
    # Round-9 finding (/tmp/review9/adversarial include): the body fingerprint hashed External.v but
    # not the header it includes, so changing `K` in the header was `identical: true`.
    r = _diff(probe, "include0", "include1")
    assert r["summary"]["identical"] is False and r["summary"]["undetermined"] == 0, r["summary"]
    (c,) = [c for c in r["components"]["changed"] if c["path"] == "b"]
    assert c["changes"]["blackbox"]["old"] != c["changes"]["blackbox"]["new"]
    assert _diff(probe, "include0", "include0")["summary"]["identical"] is True
    a = DesignDB(probe("include0"))
    try:
        (from_,) = a.q("SELECT body_from FROM blackboxes")[0]
    finally:
        a.close()
    assert "external.svh" in from_ and "context" in from_, from_


# --------------------------------------------------------------- round 10: conditions and tags
def test_diff_sees_the_case_keys_that_block_a_switch_default(probe):
    # Round-10 finding (/tmp/review10-a/default-diff.json): `switch(sel) { is(0) {} default { y := True } }`
    # vs `is(1) {}` was `identical: true`; the default's key had no case keys. The same through a
    # compiler temporary (`$gen` key), and two overlapping masked cases in swapped order.
    for old, new in (("default0", "default1"), ("default_temp0", "default_temp1"), ("overlap0", "overlap1")):
        r = _diff(probe, old, new)
        assert r["summary"]["identical"] is False and r["summary"]["undetermined"] == 0, (old, r["summary"])
        assert "io_y" in {c["path"] for c in r["assignments"]["changed"]}, (old, r["assignments"])
        assert _diff(probe, old, old)["summary"]["identical"] is True, old


def test_diff_sees_tags_of_a_generated_register_read_as_a_clock_enable(probe):
    # Round-10 finding (/tmp/review10-a/tagclock-expr-diff.json): `clockEnable = RegNext(!en)` with
    # `init` attribute 0 vs 1 (a power-on value in Yosys) was `identical: true`.
    r = _diff(probe, "tagclock0", "tagclock1")
    assert r["summary"]["identical"] is False and r["summary"]["undetermined"] == 0, r["summary"]
    (reg,) = [c for c in r["registers"]["changed"] if c["path"] == "area_inner_r"]
    assert "clock_domain_logic" in reg["changes"], reg
    assert _diff(probe, "tagclock0", "tagclock0")["summary"]["identical"] is True
    # A tag whose payload SpinalDB cannot read as content: undetermined, even against itself.
    same = _diff(probe, "tagclock_hidden", "tagclock_hidden")
    assert same["summary"]["identical"] is None and "area_inner_r" in same["undetermined"]["paths"], same["summary"]
    assert _diff(probe, "tagclock0", "tagclock_hidden")["summary"]["identical"] is not True


def test_diff_sees_component_attributes(probe):
    # Audit (round 10): instance and definition attributes of a component are emitted into the Verilog.
    for new, field in (("comp_attr1", "keep_hierarchy"), ("comp_attr2", "dont_touch")):
        r = _diff(probe, "comp_attr0", new)
        assert r["summary"]["identical"] is False, r["summary"]
        (c,) = [c for c in r["components"]["changed"] if c["path"] == "c"]
        assert c["changes"]["tags"]["old"] is None and field in c["changes"]["tags"]["new"], c
    assert _diff(probe, "comp_attr1", "comp_attr1")["summary"]["identical"] is True


def test_mcp_query_keeps_a_database_open_while_a_call_uses_it(gcd_db, tmp_path):
    """Each call owns its captured database and closes it when the call ends."""
    import os
    import shutil
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from rvw.query import mcp_tools as m
    db = tmp_path / "design.db"
    shutil.copy(gcd_db, db)
    entered, updated = threading.Event(), threading.Event()
    seen = {}

    def active(d):
        entered.set()
        assert updated.wait(10)
        seen["old"] = d
        return d.q("select count(*) from signals")

    def rebuild_then_query():
        assert entered.wait(10)
        st = db.stat()
        os.utime(db, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        try:
            return m._wrap(lambda d: d.q("select count(*) from signals"))(db=str(db))
        finally:
            updated.set()

    with ThreadPoolExecutor(2) as ex:
        a = ex.submit(m._wrap(active), db=str(db))
        b = ex.submit(rebuild_then_query)
        new, old = b.result(timeout=20), a.result(timeout=20)
    assert new == old and new[0][0] > 0
    # The first call closes its own connection without affecting the second call.
    with pytest.raises(Exception, match="closed"):
        seen["old"].q("select 1")
    assert m._wrap(lambda d: d.q("select 1"))(db=str(db)) == [(1,)]


@pytest.mark.parametrize("fail", [False, True])
def test_mcp_build_releases_database_and_capture(gcd_db, monkeypatch, fail):
    import sqlite3
    from rvw.query import mcp_tools as m

    opened = []

    def inspect(db):
        opened.append(db)
        if fail:
            raise QueryError("cannot inspect build")
        return {"db": str(db.path)}

    class Job:
        def set_progress(self, _message):
            pass

        def run(self, _command):
            return 0

    monkeypatch.setattr(m.ops, "info", inspect)
    if fail:
        with pytest.raises(QueryError, match="cannot inspect build"):
            m._build_db(str(gcd_db), design="test.Top", job=Job())
    else:
        result = m._build_db(str(gcd_db), design="test.Top", job=Job())
        assert result["db"] == str(gcd_db)
    (db,) = opened
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.q("SELECT 1")
    assert not db.input.copy.exists()


def test_mcp_copied_database_keeps_its_own_input_identity(gcd_db, tmp_path):
    import shutil
    from rvw.query import mcp_tools as m

    copied = tmp_path / "copy.db"
    shutil.copyfile(gcd_db, copied)
    query = m._wrap(ops.info)
    first, second = query(db=str(gcd_db)), query(db=str(copied))
    assert first["input_capture"]["files"][0]["sha256"] == second["input_capture"]["files"][0]["sha256"]
    assert first["db"] == str(gcd_db)
    assert second["db"] == str(copied)
    assert second["input_capture"]["files"][0]["source"] == str(copied)
