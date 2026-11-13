"""Consistency checks of probe events against the C2 trace of the same run.

Each check compares two independent sources: what the core's port did (probe events) and
what the RVFI monitor says retired (C2). `consistent` only says that they agree; it is not a
proof of the bus or CSR logic. Missing evidence is `inconclusive`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .convert import _check_identity, _hex, _int, read_c2
from .events import Stream


def _write(out, data: dict) -> dict:
    with Path(out).open("x") as f:
        json.dump(data, f, indent=1)
    return data


def _complete(stream: Stream, evs: list[dict]) -> bool:
    return bool(stream.end) and any(e.get("event") == "end" for e in evs)


def _bus_probe(stream: Stream, name: str | None):
    probes = [p for p in stream.of_kind("bus") if (name is None and "write" in dict(p.fields)) or p.name == name]
    if len(probes) != 1:
        raise ValueError(f"expected one data bus probe (a bus probe with a write field{', named ' + name if name else ''}),"
                         f" found {len(probes)}" + ("; select one with --probe" if len(probes) > 1 else ""))
    return probes[0]


def _bus_bytes(v: dict, widths: dict) -> dict[int, int | None]:
    """Byte address -> written byte (None for reads) of one bus request."""
    lanes = max(1, widths.get("data", 32) // 8)
    address = v["address"]
    if "mask" in v:
        base = address - address % lanes
        picked = [i for i in range(lanes) if v["mask"] >> i & 1]
    else:
        size = 1 << v.get("size", (lanes - 1).bit_length())
        base, picked = address, list(range(size))
    data = v.get("data", 0)
    write = bool(v.get("write", 0))
    return {base + i: (data >> (8 * i) & 255 if write else None) for i in picked}


def _c2_bytes(r: dict, write: bool) -> dict[int, int | None]:
    mask = _int(r["mem_wmask" if write else "mem_rmask"])
    address, data = _int(r["mem_addr"]), _int(r.get("mem_wdata", 0))
    return {address + i: (data >> (8 * i) & 255 if write else None) for i in range(mask.bit_length()) if mask >> i & 1}


def bus(stream: Stream, c2_path, out, probe: str | None = None) -> dict:
    """`rvw.probe-bus-check/1`: data bus requests against C2 memory accesses.

    Stores must match retired C2 stores one to one, in order, by bytes and values. Each
    retired C2 load must be covered by a later bus read, in order; reads that no load uses are
    counted (speculative or wrong-path). The probe must sit before any cache."""
    header, recs, evs = read_c2(c2_path)
    _check_identity(stream, header)
    p = _bus_probe(stream, probe)
    widths = dict(p.fields)
    reads, writes = [], []
    for cycle, q, v in stream.events("bus"):
        if q.id != p.id:
            continue
        (writes if v.get("write") else reads).append((cycle, _bus_bytes(v, widths)))
    stores = [(r["order"], _c2_bytes(r, True)) for r in recs if not r.get("trap") and _int(r.get("mem_wmask", 0))]
    loads = [(r["order"], _c2_bytes(r, False)) for r in recs if not r.get("trap") and _int(r.get("mem_rmask", 0))]
    mismatches = []
    for n, ((cycle, got), (order, want)) in enumerate(zip(writes, stores)):
        if got != want:
            mismatches.append({"store": n, "order": order, "cycle": cycle,
                               "bus": {_hex(a): b for a, b in sorted(got.items())},
                               "c2": {_hex(a): b for a, b in sorted(want.items())}})
    if len(writes) != len(stores):
        mismatches.append({"count": {"bus_writes": len(writes), "c2_stores": len(stores)}})
    i = 0
    for order, want in loads:
        while i < len(reads) and not set(want) <= set(reads[i][1]):
            i += 1
        if i == len(reads):
            mismatches.append({"load": order, "reason": "no later bus read covers the C2 load bytes",
                               "bytes": [_hex(a) for a in sorted(want)]})
            break
        i += 1
    matched_reads = i if not any("load" in m for m in mismatches) else None
    complete = _complete(stream, evs)
    status = "mismatch" if mismatches else ("consistent" if complete and (stores or loads) else "inconclusive")
    data = {"schema": "rvw.probe-bus-check/1", "status": status, "probe": p.name, "bus_reads": len(reads),
            "bus_writes": len(writes), "c2_loads": len(loads), "c2_stores": len(stores),
            "unretired_reads": None if matched_reads is None else len(reads) - len(loads), "mismatches": mismatches[:50]}
    if status == "inconclusive":
        data["reason"] = "no retired loads or stores" if complete else "incomplete probe stream or C2 trace"
    return _write(out, data)


def _csr_write(insn: int) -> tuple[int, str] | None:
    """(CSR address, form) when the instruction writes its CSR, else None."""
    if insn & 0x7f != 0x73:
        return None
    f3, rs1 = insn >> 12 & 7, insn >> 15 & 31
    if f3 in (1, 5) or (f3 in (2, 3, 6, 7) and rs1):
        return insn >> 20, ("csrrw", "csrrs", "csrrc", "", "csrrwi", "csrrsi", "csrrci")[f3 - 1]
    return None


def _expected(r: dict, form: str, xlen: int) -> int | None:
    """The value the instruction writes, from C2 operands; None when C2 cannot give it."""
    insn, mask = _int(r["insn"]), (1 << xlen) - 1
    src = insn >> 15 & 31 if form.endswith("i") else _int(r.get("rs1_rdata", 0))
    if form in ("csrrw", "csrrwi"):
        return src & mask
    if not r.get("rd"):
        return None  # the old value is not in C2
    old = _int(r["rd_wdata"])
    return (old | src) & mask if form in ("csrrs", "csrrsi") else old & ~src & mask


def csr_writes(stream: Stream, c2_path, out, probe: str | None = None) -> dict:
    """`rvw.probe-csr-writes/1`: CSR write probe events against C2 CSR instructions.

    Each retired C2 instruction that writes a CSR must match the next write event: same
    address, and the same value when C2 operands give it. A write event with no retired match
    is allowed only for an access that trapped: a trapped C2 record at that point, or a C2
    exception event before the next retirement (the core can strobe the write of an illegal
    access that then traps)."""
    header, recs, evs = read_c2(c2_path)
    _check_identity(stream, header)
    probes = [q for q in stream.of_kind("csr") if probe is None or q.name == probe]
    if len(probes) != 1:
        raise ValueError(f"expected one csr probe, found {len(probes)}" + ("; select one with --probe" if probes else ""))
    pid, xlen = probes[0].id, int(header.get("xlen", 64))
    events = [(c, v["address"], v["value"]) for c, q, v in stream.events("csr") if q.id == pid]
    wanted = [(r, *w) for r in recs if (w := _csr_write(_int(r["insn"])))]
    exceptions = [(int(e["cycle"]), _int(e.get("cause", 0)), _int(e.get("tval", 0)))
                  for e in evs if e.get("event") == "trap" and not e.get("intr")]

    def trapped(event, limit) -> bool:
        """The write event belongs to an access that trapped: a C2 exception follows it before
        the next retirement, and an illegal-instruction tval (when it holds a CSR write) names
        the same CSR."""
        for cycle, cause, tval in exceptions:
            if event[0] <= cycle <= limit:
                w = _csr_write(tval) if cause == 2 else None
                return w is None or w[0] == event[1]
        return False

    mismatches, checked, unchecked, trapped_events = [], 0, 0, 0
    i = 0
    for r, address, form in wanted:
        if r.get("trap"):
            # A trapped access may or may not strobe the write port; take one event if it is there.
            if i < len(events) and events[i][1] == address:
                i += 1
                trapped_events += 1
            continue
        limit = int(r.get("cycle", 1 << 62))
        while i < len(events) and events[i][1] != address and trapped(events[i], limit):
            i += 1
            trapped_events += 1
        if i == len(events):
            mismatches.append({"order": r["order"], "csr": _hex(address), "reason": "no write event"})
            break
        cycle, got_address, value = events[i]
        i += 1
        if got_address != address:
            mismatches.append({"order": r["order"], "cycle": cycle, "csr": _hex(address), "event_csr": _hex(got_address)})
            break
        want = _expected(r, form, xlen)
        if want is None:
            unchecked += 1
        elif want != value:
            mismatches.append({"order": r["order"], "cycle": cycle, "csr": _hex(address), "form": form,
                               "value": _hex(value), "expected": _hex(want)})
        else:
            checked += 1
    while not mismatches and i < len(events) and trapped(events[i], 1 << 62):
        i += 1
        trapped_events += 1
    if not mismatches and i < len(events):
        mismatches.append({"extra_events": len(events) - i, "first_cycle": events[i][0], "csr": _hex(events[i][1])})
    complete = _complete(stream, evs)
    status = "mismatch" if mismatches else ("consistent" if complete and wanted else "inconclusive")
    data = {"schema": "rvw.probe-csr-writes/1", "status": status, "probe": probes[0].name, "events": len(events),
            "c2_writes": sum(1 for r, *_ in wanted if not r.get("trap")),
            "c2_trapped": sum(1 for r, *_ in wanted if r.get("trap")), "trapped_events": trapped_events,
            "values_checked": checked, "values_unchecked": unchecked, "mismatches": mismatches[:50]}
    if status == "inconclusive":
        data["reason"] = "no CSR writes retired" if complete else "incomplete probe stream or C2 trace"
    return _write(out, data)
