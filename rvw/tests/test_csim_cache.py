"""rvw csim compare-cache and the cache write-policy keys (builds the native library)."""
import json

import pytest

from rvw.cli import main
from rvw.csim import rtl_cache


def write(path, lines):
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


STUDY = {"schema": "rvw.csim-study/1", "name": "dm",
         "memory": {"dram_latency": 4, "l1d": {"size_kib": 1, "ways": 1, "line_bytes": 32, "latency": 1,
                                                "write_allocate": False, "write_back": False},
                    "l1i": {"size_kib": 1, "ways": 1, "line_bytes": 32, "latency": 1}}}


def access_probe():
    return {"id": 0, "kind": "cache", "name": "dcache_access", "meta": {"cache": "dcache", "event": "access"},
            "fields": [["address", 32], ["hit", 1], ["write", 1]]}


def load(order, address, cycle=None, store=False):
    r = {"order": order, "cycle": cycle if cycle is not None else 10 + order, "pc": hex(0x100 + 4 * order),
         "pc_next": hex(0x104 + 4 * order), "insn": "0x3", "mode": 3, "trap": False, "rd": 0, "mem_addr": hex(address)}
    r["mem_wmask" if store else "mem_rmask"] = 15
    return r


def setup(tmp_path, rtl_rows, records, end=100):
    (tmp_path / "s.json").write_text(json.dumps(STUDY))
    head = {"schema": "rvw.probe-events/1", "identity": {"elf_sha256": "aa"}, "probes": [access_probe()]}
    ev = write(tmp_path / "ev.jsonl", [head, *rtl_rows, {"end": True, "cycles": end, "counters": {}, "events": {}}])
    c2 = write(tmp_path / "rvfi.jsonl", [{"schema": "rvw.rvfi/1", "xlen": 32, "elf_sha256": "aa"}, *records, {"event": "end"}])
    return tmp_path / "s.json", c2, ev


def test_store_miss_does_not_allocate_and_disagreement_is_counted(tmp_path):
    # store miss (no allocation), load miss, load hit; the RTL claims the last load missed.
    recs = [load(0, 0x2000, store=True), load(1, 0x2000), load(2, 0x2004)]
    rows = [[20, 0, 0x2000, 0, 1], [21, 0, 0x2000, 0, 0], [22, 0, 0x2004, 0, 0]]
    rep = rtl_cache.compare(*setup(tmp_path, rows, recs), cache="dcache")
    s = rep["summary"]
    assert rep["status"] == "compared" and s["accesses"] == 3
    assert s["both_miss"] == 2 and s["model_hit_rtl_miss"] == 1 and s["agreement"] == pytest.approx(2 / 3)
    assert s["rtl_miss_rate"] == 1.0 and s["miss_rate_error"] == pytest.approx(-1 / 3)
    assert rep["first_disagreements"][0]["order"] == 2 and rep["model_stats"]["write_allocate"] is False


def test_misaligned_line_and_missing_events_are_inconclusive(tmp_path):
    recs = [load(0, 0x2000), load(1, 0x3000)]
    rep = rtl_cache.compare(*setup(tmp_path, [[20, 0, 0x2000, 0, 0], [21, 0, 0x4000, 0, 0]], recs))
    assert rep["status"] == "inconclusive" and rep["misaligned"]["index"] == 1
    sub = tmp_path / "x"
    sub.mkdir()
    rep = rtl_cache.compare(*setup(sub, [[20, 0, 0x2000, 0, 0]], [load(0, 0x2000), load(1, 0x2000, cycle=50)]))
    assert rep["status"] == "inconclusive" and "1 RTL access events for 2" in rep["reasons"][0]


def test_unsampled_tail_at_the_end_of_the_run(tmp_path):
    rep = rtl_cache.compare(*setup(tmp_path, [[20, 0, 0x2000, 0, 0]], [load(0, 0x2000), load(1, 0x2000, cycle=98)]))
    assert rep["status"] == "inconclusive" and rep["unsampled_tail"] == 1


def test_cli_writes_the_aligned_trace(tmp_path, capsys):
    study, c2, ev = setup(tmp_path, [[20, 0, 0x2000, 0, 0], [21, 0, 0x2004, 1, 0]], [load(0, 0x2000), load(1, 0x2004)])
    out = tmp_path / "t.csim"
    assert main(["csim", "compare-cache", str(study), "--trace", str(c2), "--events", str(ev),
                 "--trace-out", str(out), "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["summary"]["agreement"] == 1.0
    assert out.read_text().splitlines() == ["rvw.csim-trace/1", out.read_text().splitlines()[1],
                                            "L 1 100 2000 4", "L 2 104 2004 4", "END 2"]


def test_compare_rtl_cache_option(tmp_path, capsys):
    study, c2, ev = setup(tmp_path, [[20, 0, 0x2000, 0, 0]], [load(0, 0x2000)])
    assert main(["csim", "compare-rtl", str(study), "--trace", str(c2), "--events", str(ev),
                 "--cache", "dcache", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["accesses"] == 1


def test_incomplete_c2_and_wrong_store_direction(tmp_path):
    study, c2, ev = setup(tmp_path, [[20, 0, 0x2000, 0, 1]], [load(0, 0x2000)])
    assert rtl_cache.compare(study, c2, ev)["status"] == "inconclusive"
    c2.write_text("\n".join(c2.read_text().splitlines()[:-1]) + "\n")
    rep = rtl_cache.compare(study, c2, ev)
    assert "incomplete C2 trace (no end record)" in rep["reasons"]
