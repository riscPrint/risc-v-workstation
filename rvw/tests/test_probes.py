"""rvw probes: event stream reader, consumer matrix, converters and CLI (synthetic streams)."""
import csv
import json
import sqlite3

import pytest

from rvw.cli import main
from rvw.perf import kanata as kreader
from rvw.probes import api, convert as cv
from rvw.probes.events import read

BEQ = 0x00000463  # beq x0, x0, +8
ADD = 0x00000033


def write(path, lines):
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def probe(i, kind, name, fields, **meta):
    return {"id": i, "kind": kind, "name": name, "fields": [[f, 32] for f in fields], "meta": meta}


def stream(tmp_path, probes, rows, end=True, counters=None, elf="aa"):
    lines = [{"schema": "rvw.probe-events/1", "identity": {"elf_sha256": elf}, "probes": probes}] + rows
    if end:
        lines.append({"end": True, "cycles": 100, "counters": counters or {}, "events": {}})
    return write(tmp_path / "probe-events.jsonl", lines)


def c2(tmp_path, records, events=(), name="rvfi.jsonl"):
    head = {"schema": "rvw.rvfi/1", "xlen": 32, "core": "x", "config": "c", "elf_sha256": "aa"}
    return write(tmp_path / name, [head, *records, *events, {"event": "end", "cycle": 99, "status": "pass"}])


def rec(order, pc, insn, nxt, cycle=None):
    return {"order": order, "cycle": cycle or 10 + order, "pc": hex(pc), "pc_next": hex(nxt), "insn": hex(insn),
            "mode": 3, "trap": False, "rd": 0}


BRANCH = probe(0, "branch", "bp", ["pc", "taken", "target", "predicted_taken"], semantics="final-prediction",
               covers="cond,jump,ijump,call,icall,ret")


def test_bp_events_align_with_c2(tmp_path):
    trace = c2(tmp_path, [rec(0, 0x100, ADD, 0x104), rec(1, 0x104, BEQ, 0x10c), rec(2, 0x10c, ADD, 0x110)])
    ev = stream(tmp_path, [BRANCH], [[11, 0, 0x104, 1, 0x10c, 0]])
    out = tmp_path / "bp.jsonl"
    rep = api.run_convert(ev, "bp-events", out, c2=trace)
    assert rep["rows"] == 1 and rep["kinds"] == {"direction_misses": 1, "cond": 1}
    head, row = [json.loads(x) for x in out.read_text().splitlines()]
    assert head["schema"] == "rvw.bp-events/1" and head["counter_semantics"] == "final-prediction"
    assert head["elf_sha256"] == "aa" and head["hart"] == 0
    assert row == {"order": 1, "pc": "0x104", "kind": "cond", "taken": True, "target": "0x10c", "predicted_taken": False}
    from rvw.csim.rtl import read_bp_events
    _, rows = read_bp_events(out)
    assert rows[1]["direction"] == (False, True)


def test_bp_events_refuse_speculative_or_misaligned(tmp_path):
    trace = c2(tmp_path, [rec(0, 0x104, BEQ, 0x10c)])
    extra = stream(tmp_path, [BRANCH], [[10, 0, 0x104, 1, 0x10c, 1], [11, 0, 0x104, 1, 0x10c, 1]])
    with pytest.raises(ValueError, match="2 branch events but 1"):
        api.run_convert(extra, "bp-events", tmp_path / "a.jsonl", c2=trace)
    wrong = stream(tmp_path, [BRANCH], [[10, 0, 0x200, 1, 0x10c, 1]])
    with pytest.raises(ValueError, match="does not match"):
        api.run_convert(wrong, "bp-events", tmp_path / "b.jsonl", c2=trace)
    taken = stream(tmp_path, [BRANCH], [[10, 0, 0x104, 0, 0x10c, 1]])
    with pytest.raises(ValueError, match="taken outcome"):
        api.run_convert(taken, "bp-events", tmp_path / "c.jsonl", c2=trace)
    other = stream(tmp_path, [BRANCH], [[10, 0, 0x104, 1, 0x10c, 1]], elf="bb")
    with pytest.raises(ValueError, match="different ELF"):
        api.run_convert(other, "bp-events", tmp_path / "d.jsonl", c2=trace)


def test_kanata_from_stages_is_readable_by_perf(tmp_path):
    probes = [probe(0, "stage", "decode", ["id", "pc"], stage="D", lane="0"),
              probe(1, "stage", "execute", ["id"], stage="X", lane="0"),
              probe(2, "retire", "wb", ["id"]), probe(3, "flush", "kill", ["id"]),
              probe(4, "stall", "issue_operand_wait", [], scope="issue", cause="operand_wait", evidence="measured")]
    probes[4]["fields"] = []
    rows = [[1, 0, 7, 0x100], [2, 0, 7, 0x100], [2, 4], [3, 1, 7], [3, 0, 8, 0x104], [4, 2, 7], [4, 3, 8],
            [5, 0, 7, 0x108], [6, 2, 7]]
    ev = stream(tmp_path, probes, rows)
    out = tmp_path / "k.log"
    rep = api.run_convert(ev, "kanata", out)
    assert rep == {"format": "Kanata 0004", "instructions": 3, "retired": 2, "flushed": 1, "stall_samples": 1, "open": 0}
    t = kreader.read(out)
    assert len(t.instructions) == 3
    assert sum(1 for i in t.instructions.values() if i.flushed) == 1
    assert [s.stage for s in t.instructions["0"].spans] == ["D", "X"]
    assert t.instructions["0"].labels["0"].startswith("100:")
    assert len(t.stalls) == 1


def test_mmu_cache_counts_hpm_ingress(tmp_path):
    probes = [probe(0, "tlb", "dtlb_fill", ["va", "pa", "asid", "entry", "size", "pte_address", "pte"], tlb="dtlb", event="fill"),
              probe(1, "tlb", "dtlb_hit", ["va", "pa", "asid", "entry"], tlb="dtlb", event="hit"),
              probe(2, "walk", "ptw_request", ["address"], walker="ptw", event="request"),
              probe(3, "cache", "dcache_access", ["address", "hit", "data"], cache="dcache", event="read"),
              probe(4, "counter", "dcache_miss", ["inc"], hpm="4"),
              probe(5, "trace", "te", ["itype", "iaddr", "iretire", "ilastsize", "priv"])]
    rows = [[1, 2, 0x1000], [2, 0, 0x4000, 0x80004000, 0, 1, 4096, 0x1000, 0xcf],
            [3, 1, 0x4010, 0x80004010, 0, 1], [4, 3, 0x80, 0, 0x04030201], [5, 5, 4, 0x80000000, 1, 1, 3]]
    ev = stream(tmp_path, probes, rows, counters={"dcache_miss": 7})
    api.run_convert(ev, "mmu", tmp_path / "mmu.jsonl")
    lines = [json.loads(x) for x in (tmp_path / "mmu.jsonl").read_text().splitlines()]
    assert lines[0]["schema"] == "rvw.mmu-observations/1"
    assert [x["kind"] for x in lines[1:]] == ["walk_request", "tlb_fill", "tlb_hit"]
    from rvw.regress.mmu_protocol import check
    fills = [dict(x) for x in lines[1:] if x["kind"].startswith("tlb")]
    result = check([{"cycle": 0, "kind": "pte_write", "address": "0x1000", "data": "0xcf"}] + fills, required_harts=[0])
    assert result.get("status") != "inconclusive" and not result.get("errors")
    rep = api.run_convert(ev, "cache", tmp_path / "cache.jsonl")
    row = json.loads((tmp_path / "cache.jsonl").read_text())
    assert row["event"] == "dcache.read" and row["bytes"] == "01020304" and row["hit"] is False
    assert rep["names"] == {"dcache.read": "read"} and rep["counts"]["dcache.read.miss"] == 1
    (tmp_path / "result.json").write_text("{}")
    trace = c2(tmp_path, [rec(0, 0x100, ADD, 0x104)])
    api.run_convert(ev, "counts", tmp_path / "counts.json", c1=tmp_path / "result.json", c2=trace)
    counts = json.loads((tmp_path / "counts.json").read_text())
    assert counts["counts"] == {"dcache_miss": 7} and len(counts["c1_sha256"]) == 64
    api.run_convert(ev, "hpm", tmp_path / "hpm.json")
    assert json.loads((tmp_path / "hpm.json").read_text())["bindings"] == [{"selector": 4, "counter": "dcache_miss", "total": 7}]
    api.run_convert(ev, "etrace-ingress", tmp_path / "in.csv")
    got = list(csv.reader((tmp_path / "in.csv").open()))
    assert got[0][0] == "itype_0" and got[1] == ["4", "0", "0", "3", "80000000", "0", "0", "1", "1"]


def test_counts_need_complete_stream(tmp_path):
    ev = stream(tmp_path, [probe(0, "counter", "x", ["inc"])], [], end=False)
    with pytest.raises(ValueError, match="no end record"):
        api.run_convert(ev, "counts", tmp_path / "c.json", c1=ev, c2=ev)


def test_interrupts_against_c2(tmp_path):
    ev = stream(tmp_path, [probe(0, "interrupt", "irq", ["cause", "pc"])], [[20, 0, 0x80000007, 0x200]])
    good = c2(tmp_path, [rec(0, 0x100, ADD, 0x104)], [{"event": "trap", "cycle": 20, "cause": "0x80000007", "tval": "0x0", "intr": True}])
    assert api.run_convert(ev, "interrupts", tmp_path / "i.json", c2=good)["status"] == "consistent"
    bad = c2(tmp_path, [rec(0, 0x100, ADD, 0x104)], [{"event": "trap", "cycle": 20, "cause": "0x8000000b", "tval": "0x0", "intr": True}], name="bad.jsonl")
    assert api.run_convert(ev, "interrupts", tmp_path / "j.json", c2=bad)["status"] == "mismatch"
    none = stream(tmp_path, [probe(0, "interrupt", "irq", ["cause", "pc"])], [])
    plain = c2(tmp_path, [rec(0, 0x100, ADD, 0x104)], name="plain.jsonl")
    assert api.run_convert(none, "interrupts", tmp_path / "k.json", c2=plain)["status"] == "inconclusive"


def test_reader_refuses_bad_rows(tmp_path):
    bad = stream(tmp_path, [BRANCH], [[5, 0, 1, 1, 1, 1], [4, 0, 1, 1, 1, 1]])
    with pytest.raises(ValueError, match="decrease"):
        read(bad)
    short = stream(tmp_path, [BRANCH], [[5, 0, 1]])
    with pytest.raises(ValueError, match="does not match"):
        read(short)


def test_list_from_db_and_matrix(tmp_path):
    db = tmp_path / "d.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE components(id INTEGER PRIMARY KEY, path TEXT)")
    con.execute("CREATE TABLE signals(id INTEGER PRIMARY KEY, component_id INTEGER, name TEXT, width INTEGER)")
    con.execute("INSERT INTO components VALUES (1, 'Top')")
    names = ["rvwprobe__branch__bp__valid", "rvwprobe__branch__bp__pc", "rvwprobe__branch__bp__taken",
             "rvwprobe__branch__bp__target", "rvwprobe__branch__bp__predicted_taken",
             "rvwprobe__counter__ret__valid", "rvwprobe__counter__ret__inc", "other_signal"]
    con.executemany("INSERT INTO signals(component_id, name, width) VALUES (1, ?, 32)", [(n,) for n in names])
    con.commit(); con.close()
    rep = api.report(db=db)
    assert [p["kind"] for p in rep["probes"]] == ["branch", "counter"]
    status = {r["consumer"]: r["status"] for r in rep["consumers"]}
    assert status["csim-compare-rtl"] == "enabled" and status["ooo-calibration"] == "enabled"
    assert status["perf-pipeline"] == "missing" and status["hpm-bindings"] == "unknown"
    assert status["cosim-csr-slots"] == "missing"
    assert "csim-compare-rtl" in rep["enabled"] and "perf-pipeline" in rep["missing"]


def test_cli(tmp_path, capsys):
    ev = stream(tmp_path, [BRANCH], [])
    assert main(["probes", "list", "--events", str(ev), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["enabled"] == ["csim-compare-rtl"]
    assert main(["probes", "summary", str(ev)]) == 0
    assert json.loads(capsys.readouterr().out)["complete"] is True
    assert main(["probes", "convert", str(ev), "--to", "bp-events", "--out", str(tmp_path / "x")]) == 2
    assert "needs --c2" in capsys.readouterr().err


def test_mcp_tools_registered():
    from rvw.probes.mcp_tools import mcp_tools
    names = {t.name for t in mcp_tools()}
    assert names == {"probes_list", "probes_summary", "probes_convert", "probes_check"}
