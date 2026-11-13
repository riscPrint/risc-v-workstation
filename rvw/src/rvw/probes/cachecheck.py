"""`rvw.probe-cache-check/1`: cache probe events against a resident-line scoreboard and an
independent memory image (the ELF plus the retired C2 stores).

Rules, per cache name (the `cache` meta of `Probe.cacheAccess`):
  * `fill` installs a line that is not resident; its bytes must equal the memory image at that
    cycle (all C2 stores retired before it applied);
  * `evict` removes a resident line; `flush` removes every line;
  * `writeback` bytes must equal the memory image at that cycle;
  * physical `access`/`lookup` hits need a resident line or independently checked refill bytes;
    retired-refill attribution needs a separate physical lookup stream.
  * a legacy `access` with `hit` true needs its line resident (a hit on a line never filled is a
    false hit);
  * with a geometry (sets x ways), a fill into a full set needs an `evict` first. A cache
    with no evict probe gets an implied eviction instead (counted; with more than one way the
    victim is unknown, so hits in that set are no longer checked).
`consistent` only says the events agree with these rules; it is not a proof of the cache.
"""
from __future__ import annotations

import bisect
from collections import defaultdict
from pathlib import Path

from .checks import _c2_bytes, _complete, _write
from .convert import _check_identity, _hex, _int, read_c2
from .events import Stream

SCHEMA = "rvw.probe-cache-check/1"


def load_elf(path) -> dict[int, int]:
    from rvw.debug.profile import load_elf as segments
    data = Path(path).read_bytes()
    xlen = 64 if data[4:5] == b"\x02" else 32
    image: dict[int, int] = {}
    for base, raw in segments(path, xlen):
        for i, b in enumerate(raw):
            image[base + i] = b
    return image


def parse_geometry(items) -> dict[str, tuple[int, int]]:
    out = {}
    for item in items or []:
        name, _, shape = item.partition("=")
        sets, _, ways = shape.lower().partition("x")
        if not name or not sets.isdigit() or not ways.isdigit() or int(sets) < 1 or int(ways) < 1:
            raise ValueError(f"--geometry needs CACHE=SETSxWAYS, got {item!r}")
        out[name] = (int(sets), int(ways))
    return out


class _Oracle:
    """Memory image with the C2 stores applied in retirement order up to a cycle."""

    def __init__(self, image: dict[int, int], stores: list[tuple[int, dict[int, int]]]):
        self.image, self.stores, self.applied = dict(image), stores, 0
        self.cycles = [c for c, _ in stores]

    def at(self, cycle: int) -> "_Oracle":
        stop = bisect.bisect_left(self.cycles, cycle)
        while self.applied < stop:
            self.image.update(self.stores[self.applied][1])
            self.applied += 1
        return self

    def read(self, address: int, n: int) -> bytes:
        return bytes(self.image.get(address + i, 0) for i in range(n))


def check(stream: Stream, c2_path, out, elf=None, geometry: dict[str, tuple[int, int]] | None = None) -> dict:
    header, recs, evs = read_c2(c2_path)
    _check_identity(stream, header)
    elf = elf or stream.identity.get("elf")
    if not elf or not Path(elf).is_file():
        raise ValueError("the cache check needs the run's ELF (stream identity or --elf)")
    stores = sorted(((int(r["cycle"]), {a: b for a, b in _c2_bytes(r, True).items()})
                     for r in recs if not r.get("trap") and _int(r.get("mem_wmask", 0))), key=lambda s: s[0])
    oracle = _Oracle(load_elf(elf), stores)
    geometry = geometry or {}
    probes = {p.id: p for p in stream.of_kind("cache")}
    caches = sorted({p.meta.get("cache") for p in probes.values()})
    if not caches:
        raise ValueError("probe stream has no cache probes")
    has_evict = {c: any(p.meta.get("cache") == c and p.meta.get("event") == "evict" for p in probes.values()) for c in caches}
    line_bytes: dict[str, int] = {}
    for p in probes.values():
        if p.meta.get("event") in ("fill", "writeback") and "data" in dict(p.fields):
            line_bytes[p.meta["cache"]] = dict(p.fields)["data"] // 8
    partial = {c: set() for c in caches}
    resident: dict[str, set[int]] = {c: set() for c in caches}
    uncertain: dict[str, set[int]] = {c: set() for c in caches}
    counts: dict[str, dict] = {c: defaultdict(int) for c in caches}
    mismatches: list[dict] = []

    def bad(cache, cycle, rule, **kw):
        counts[cache]["violations"] += 1
        if len(mismatches) < 50:
            mismatches.append({"cache": cache, "cycle": cycle, "rule": rule, **kw})

    for cycle, p, v in stream.events("cache"):
        cache, event = p.meta.get("cache"), p.meta.get("event")
        lb = line_bytes.get(cache)
        if lb is None:
            counts[cache]["unchecked_no_line_size"] += 1
            continue
        line = v["address"] - v["address"] % lb
        sets, ways = geometry.get(cache, (None, None))
        set_of = (lambda a: (a // lb) % sets) if sets else None
        c = counts[cache]
        c[event] += 1
        if event == "refill_beat":
            size = dict(p.fields).get("data", 0) // 8
            if not size:
                bad(cache, cycle, "refill beat has no data", address=_hex(v["address"]))
            else:
                got = v["data"].to_bytes(size, "little")
                want = oracle.at(cycle).read(v["address"], size)
                c["refill_beats_checked"] += 1
                if got != want:
                    bad(cache, cycle, "refill beat differs from memory", address=_hex(v["address"]))
                partial[cache].update(range(v["address"], v["address"] + size))
        elif event == "fill":
            if line in resident[cache]:
                bad(cache, cycle, "duplicate fill", line=_hex(line))
            elif sets:
                peers = [a for a in resident[cache] if set_of(a) == set_of(line)]
                if len(peers) >= ways:
                    if has_evict[cache]:
                        bad(cache, cycle, "fill into a full set without an eviction", line=_hex(line),
                            resident=[_hex(a) for a in sorted(peers)])
                    else:
                        c["implied_evictions"] += 1
                        if ways == 1:
                            resident[cache].discard(peers[0])
                        else:
                            resident[cache].difference_update(peers)
                            uncertain[cache].add(set_of(line))
            resident[cache].add(line)
            partial[cache].difference_update(range(line, line + lb))
            if "data" in v:
                got = v["data"].to_bytes(lb, "little")
                want = oracle.at(cycle).read(line, lb)
                c["fill_data_checked"] += 1
                if got != want:
                    bad(cache, cycle, "fill data differs from memory", line=_hex(line),
                        bytes=[i for i in range(lb) if got[i] != want[i]][:8])
        elif event == "evict":
            if line not in resident[cache]:
                if not (sets and set_of(line) in uncertain[cache]):
                    bad(cache, cycle, "eviction of a line that is not resident", line=_hex(line))
            resident[cache].discard(line)
            partial[cache].difference_update(range(line, line + lb))
        elif event == "writeback":
            if "data" in v:
                got = v["data"].to_bytes(lb, "little")
                want = oracle.at(cycle).read(line, lb)
                c["writeback_data_checked"] += 1
                if got != want:
                    bad(cache, cycle, "writeback data differs from memory", line=_hex(line),
                        bytes=[i for i in range(lb) if got[i] != want[i]][:8])
        elif event == "flush" and p.meta.get("semantics") != "writeback-only":
            resident[cache].clear()
            partial[cache].clear()
            uncertain[cache].clear()
        elif event == "access" and p.meta.get("semantics") == "retired-refill-attribution":
            # A buffered instruction can retire after its line was invalidated.
            # This stream attributes refill cost; it is not a physical tag lookup.
            c["retired_accesses_not_residency_checks"] += 1
        elif event in ("access", "lookup") and "hit" in v:
            if v["hit"]:
                if sets and set_of(line) in uncertain[cache]:
                    c["hits_unchecked"] += 1
                elif line not in resident[cache]:
                    size = dict(p.fields).get("data", 0) // 8
                    needed = set(range(v["address"], v["address"] + size))
                    if size and needed <= partial[cache]:
                        c["early_restart_hits_checked"] += 1
                        if v["data"].to_bytes(size, "little") != oracle.at(cycle).read(v["address"], size):
                            bad(cache, cycle, "early restart data differs from memory", address=_hex(v["address"]))
                    else:
                        bad(cache, cycle, "hit on a line that is not resident", line=_hex(line), address=_hex(v["address"]))
                else:
                    c["hits_checked"] += 1
            else:
                c["misses"] += 1
    complete = _complete(stream, evs)
    checked = sum(c["fill_data_checked"] + c["hits_checked"] + c["writeback_data_checked"] + c["early_restart_hits_checked"] for c in counts.values())
    missing_lookup = any(c["retired_accesses_not_residency_checks"] and not c["lookup"] for c in counts.values())
    status = "mismatch" if mismatches else ("consistent" if complete and checked and not missing_lookup else "inconclusive")
    data = {"schema": SCHEMA, "status": status, "elf": str(elf), "c2_stores": len(stores),
            "geometry": {k: {"sets": s, "ways": w} for k, (s, w) in geometry.items()},
            "caches": {k: {"line_bytes": line_bytes.get(k), "evict_probe": has_evict[k], **dict(v)} for k, v in counts.items()},
            "mismatches": mismatches}
    if status == "inconclusive":
        data["reason"] = ("retired access attribution needs physical lookup events for residency checks" if missing_lookup else
                          "nothing checked (no fill data or hits)" if complete else "incomplete probe stream or C2 trace")
    return _write(out, data)
