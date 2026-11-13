"""rvw probes bus and CSR-write checks against C2 (synthetic streams)."""
import json

import pytest

from rvw.probes import api

pytestmark = pytest.mark.fast

SW = 0x00512023     # sw t0, 0(sp)
LW = 0x00012283     # lw t0, 0(sp)
CSRRW = 0x34029073  # csrrw x0, mscratch, t0
CSRRS_RD = 0x340322f3  # csrrs t0, mscratch, t1
CSRRS_X0 = 0x340022f3  # csrrs t0, mscratch, x0 (no write)
CSRW_SATP = 0x18001073  # csrw satp, x0


def write(path, lines):
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def stream(tmp_path, probes, rows, name="probe-events.jsonl", end=True):
    lines = [{"schema": "rvw.probe-events/1", "identity": {"elf_sha256": "aa"}, "probes": probes}] + rows
    if end:
        lines.append({"end": True, "cycles": 100, "counters": {}, "events": {}})
    return write(tmp_path / name, lines)


def c2(tmp_path, records, name="rvfi.jsonl"):
    head = {"schema": "rvw.rvfi/2", "xlen": 32, "core": "x", "config": "c", "elf_sha256": "aa"}
    return write(tmp_path / name, [head, *records, {"event": "end", "cycle": 99, "status": "pass"}])


def rec(order, insn, **kw):
    r = {"order": order, "cycle": 10 + order, "pc": hex(0x100 + 4 * order), "pc_next": hex(0x104 + 4 * order),
         "insn": hex(insn), "mode": 3, "trap": False, "rd": 0, "rd_wdata": "0x0", "rs1_rdata": "0x0",
         "mem_addr": "0x0", "mem_rmask": 0, "mem_wmask": 0, "mem_wdata": "0x0"}
    r.update(kw)
    return r


DBUS = {"id": 0, "kind": "bus", "name": "dbus", "meta": {"bus": "dbus"},
        "fields": [["address", 32], ["write", 1], ["data", 32], ["mask", 4], ["size", 2]]}
IBUS = {"id": 1, "kind": "bus", "name": "ibus", "meta": {"bus": "ibus"}, "fields": [["address", 32]]}
CSR = {"id": 0, "kind": "csr", "name": "csr", "meta": {}, "fields": [["address", 12], ["value", 32]]}


def test_bus_matches_stores_and_loads_with_speculative_reads(tmp_path):
    ev = stream(tmp_path, [DBUS, IBUS], [
        [5, 1, 0x100],
        [10, 0, 0x2000, 1, 0x11223344, 0xf, 2],    # store word
        [12, 0, 0x3000, 0, 0, 0xf, 2],             # wrong-path read
        [14, 0, 0x2000, 0, 0, 0xf, 2],             # the load
    ])
    trace = c2(tmp_path, [rec(0, SW, mem_addr="0x2000", mem_wmask=15, mem_wdata="0x11223344"),
                          rec(1, LW, rd=5, mem_addr="0x2000", mem_rmask=15)])
    rep = api.run_convert(ev, "bus", tmp_path / "b.json", c2=trace)
    assert rep["status"] == "consistent" and rep["unretired_reads"] == 1 and rep["c2_stores"] == 1


def test_bus_reports_store_value_and_extra_write(tmp_path):
    ev = stream(tmp_path, [DBUS], [[10, 0, 0x2000, 1, 0x11223345, 0xf, 2], [11, 0, 0x2004, 1, 0, 0x1, 0]])
    trace = c2(tmp_path, [rec(0, SW, mem_addr="0x2000", mem_wmask=15, mem_wdata="0x11223344")])
    rep = api.run_convert(ev, "bus", tmp_path / "b.json", c2=trace)
    assert rep["status"] == "mismatch"
    assert rep["mismatches"][0]["store"] == 0 and rep["mismatches"][-1]["count"] == {"bus_writes": 2, "c2_stores": 1}


def test_bus_load_without_read_and_incomplete_stream(tmp_path):
    ev = stream(tmp_path, [DBUS], [])
    trace = c2(tmp_path, [rec(0, LW, rd=5, mem_addr="0x2000", mem_rmask=15)])
    assert api.run_convert(ev, "bus", tmp_path / "a.json", c2=trace)["status"] == "mismatch"
    cut = stream(tmp_path, [DBUS], [[10, 0, 0x2000, 0, 0, 0xf, 2]], name="cut.jsonl", end=False)
    assert api.run_convert(cut, "bus", tmp_path / "b.json", c2=trace)["status"] == "inconclusive"


def test_bus_needs_a_data_bus_probe(tmp_path):
    ev = stream(tmp_path, [dict(IBUS, id=0)], [])
    with pytest.raises(ValueError, match="data bus probe"):
        api.run_convert(ev, "bus", tmp_path / "b.json", c2=c2(tmp_path, [rec(0, SW)]))


def test_csr_writes_check_address_value_and_traps(tmp_path):
    ev = stream(tmp_path, [CSR], [[10, 0, 0x340, 0x55], [11, 0, 0x340, 0x7], [12, 0, 0x180, 0]])
    trace = c2(tmp_path, [
        rec(0, CSRRW, rs1_rdata="0x55"),
        rec(1, CSRRS_RD, rd=5, rd_wdata="0x5", rs1_rdata="0x2"),   # 5 | 2 = 7
        rec(2, CSRRS_X0, rd=5, rd_wdata="0x7"),                     # no write
        rec(3, CSRW_SATP, trap=True),                               # illegal: may strobe
    ])
    rep = api.run_convert(ev, "csr-writes", tmp_path / "c.json", c2=trace)
    assert rep["status"] == "consistent", rep
    assert rep["values_checked"] == 2 and rep["trapped_events"] == 1 and rep["c2_trapped"] == 1


def test_csr_writes_report_wrong_value_and_missing_event(tmp_path):
    ev = stream(tmp_path, [CSR], [[10, 0, 0x340, 0x54]])
    trace = c2(tmp_path, [rec(0, CSRRW, rs1_rdata="0x55"), rec(1, CSRRW, rs1_rdata="0x1")])
    rep = api.run_convert(ev, "csr-writes", tmp_path / "c.json", c2=trace)
    assert rep["status"] == "mismatch"
    assert rep["mismatches"][0]["expected"] == "0x55" and rep["mismatches"][1]["reason"] == "no write event"


def test_csr_writes_accept_strobe_of_trapped_access_from_c2_trap_event(tmp_path):
    ev = stream(tmp_path, [CSR], [[20, 0, 0x180, 0], [30, 0, 0x341, 0x55]])
    head = {"schema": "rvw.rvfi/2", "xlen": 32, "core": "x", "config": "c", "elf_sha256": "aa"}
    trap = {"event": "trap", "cycle": 22, "cause": "0x2", "tval": hex(CSRW_SATP), "intr": False}
    good = write(tmp_path / "g.jsonl", [head, trap, dict(rec(0, 0x34129073, rs1_rdata="0x55"), cycle=31),
                                        {"event": "end", "cycle": 99, "status": "pass"}])
    rep = api.run_convert(ev, "csr-writes", tmp_path / "c.json", c2=good)
    assert rep["status"] == "consistent" and rep["trapped_events"] == 1
    # The trap names another CSR: the event is not explained.
    other = dict(trap, tval=hex(CSRW_SATP & 0xfffff | 0x30500000))
    bad = write(tmp_path / "b.jsonl", [head, other, dict(rec(0, 0x34129073, rs1_rdata="0x55"), cycle=31),
                                       {"event": "end", "cycle": 99, "status": "pass"}])
    assert api.run_convert(ev, "csr-writes", tmp_path / "d.json", c2=bad)["status"] == "mismatch"


def test_csr_writes_report_extra_event(tmp_path):
    ev = stream(tmp_path, [CSR], [[10, 0, 0x340, 0x55], [11, 0, 0x305, 0x100]])
    trace = c2(tmp_path, [rec(0, CSRRW, rs1_rdata="0x55")])
    rep = api.run_convert(ev, "csr-writes", tmp_path / "c.json", c2=trace)
    assert rep["status"] == "mismatch" and rep["mismatches"][0]["extra_events"] == 1
