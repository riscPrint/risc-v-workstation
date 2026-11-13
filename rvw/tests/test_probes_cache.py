"""rvw probes cache-check: cache events against a scoreboard and the ELF + C2 memory image."""
import json
import struct

import pytest

from rvw.probes import api

pytestmark = pytest.mark.fast


def write(path, lines):
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def elf32(path, base, data):
    """A minimal little-endian ELF32 with one PT_LOAD segment."""
    ehdr = b"\x7fELF" + bytes([1, 1, 1]) + bytes(9)
    ehdr += struct.pack("<HHIIIIIHHHHHH", 2, 0xF3, 1, base, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    phdr = struct.pack("<IIIIIIII", 1, 84, base, base, len(data), len(data), 5, 4)
    path.write_bytes(ehdr + phdr + data)
    return path


LINE = 16
BASE = 0x1000
DATA = bytes(range(64))


def probes():
    def p(i, cache, event, fields):
        return {"id": i, "kind": "cache", "name": f"{cache}_{event}", "meta": {"cache": cache, "event": event},
                "fields": [[f, w] for f, w in fields]}
    return [p(0, "dcache", "fill", [("address", 32), ("data", LINE * 8)]),
            p(1, "dcache", "access", [("address", 32), ("hit", 1), ("write", 1)]),
            p(2, "dcache", "evict", [("address", 32)]),
            p(3, "dcache", "writeback", [("address", 32), ("data", LINE * 8)])]


def run(tmp_path, rows, records=(), geometry=None):
    elf = elf32(tmp_path / "prog", BASE, DATA)
    head = {"schema": "rvw.probe-events/1", "identity": {"elf_sha256": "aa", "elf": str(elf)}, "probes": probes()}
    ev = write(tmp_path / "ev.jsonl", [head, *rows, {"end": True, "cycles": 100, "counters": {}, "events": {}}])
    c2 = write(tmp_path / "rvfi.jsonl", [{"schema": "rvw.rvfi/1", "xlen": 32, "elf_sha256": "aa"}, *records,
                                         {"event": "end", "cycle": 99, "status": "pass"}])
    out = tmp_path / "check.json"
    return api.run_convert(ev, "cache-check", out, c2=c2, geometry=geometry)


def line(address, image=DATA):
    return int.from_bytes(image[address - BASE:address - BASE + LINE], "little")


def store(order, cycle, address, value):
    return {"order": order, "cycle": cycle, "pc": "0x0", "pc_next": "0x4", "insn": "0x23", "mode": 3, "trap": False,
            "rd": 0, "mem_addr": hex(address), "mem_wmask": 1, "mem_rmask": 0, "mem_wdata": hex(value)}


def test_consistent_fill_hit_and_store_visible_in_writeback(tmp_path):
    image = bytearray(DATA)
    image[0x10] = 0xAB
    rep = run(tmp_path, [[5, 0, BASE + 0x10, line(BASE + 0x10)], [6, 1, BASE + 0x14, 1, 0],
                         [20, 2, BASE + 0x10], [21, 3, BASE + 0x10, line(BASE + 0x10, bytes(image))]],
              records=[store(0, 10, BASE + 0x10, 0xAB)], geometry=["dcache=2x1"])
    assert rep["status"] == "consistent", rep["mismatches"]
    d = rep["caches"]["dcache"]
    assert d["fill_data_checked"] == 1 and d["hits_checked"] == 1 and d["writeback_data_checked"] == 1


def test_false_hit_stale_fill_and_full_set_are_named(tmp_path):
    rows = [[5, 1, BASE, 1, 0],                                  # hit before any fill
            [6, 0, BASE, line(BASE) ^ 1],                         # fill bytes differ from the ELF
            [7, 0, BASE + 2 * LINE, line(BASE + 2 * LINE)]]       # same set (2 sets, 1 way), no evict
    rep = run(tmp_path, rows, geometry=["dcache=2x1"])
    assert rep["status"] == "mismatch"
    rules = [m["rule"] for m in rep["mismatches"]]
    assert rules == ["hit on a line that is not resident", "fill data differs from memory",
                     "fill into a full set without an eviction"]


def test_stale_writeback_and_missing_elf(tmp_path):
    rep = run(tmp_path, [[5, 0, BASE, line(BASE)], [9, 3, BASE, line(BASE)]], records=[store(0, 7, BASE, 0x55)])
    assert rep["status"] == "mismatch" and rep["mismatches"][0]["rule"] == "writeback data differs from memory"
    head = {"schema": "rvw.probe-events/1", "identity": {"elf_sha256": "aa"}, "probes": probes()}
    ev = write(tmp_path / "e2.jsonl", [head, {"end": True, "cycles": 1, "counters": {}, "events": {}}])
    with pytest.raises(ValueError, match="ELF"):
        api.run_convert(ev, "cache-check", tmp_path / "x.json", c2=tmp_path / "rvfi.jsonl")


def test_geometry_parse():
    from rvw.probes.cachecheck import parse_geometry
    assert parse_geometry(["icache=128x1", "dcache=32X2"]) == {"icache": (128, 1), "dcache": (32, 2)}
    with pytest.raises(ValueError):
        parse_geometry(["dcache=32"])
