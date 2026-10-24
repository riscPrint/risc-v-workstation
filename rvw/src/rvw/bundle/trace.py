"""Reading the end of a C2 RVFI trace (rvfi.jsonl) and of a Konata log without loading them whole."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


def reverse_lines(path: str, chunk: int = 1 << 16, max_chunk: int = 1 << 18):
    """Non-empty lines of a text file, last first, reading backwards in growing chunks (at most
    `max_chunk` bytes). Memory stays about one chunk plus the longest line: lines are cut out of
    the buffer one at a time (review 5: splitting chunks of up to 16 MB into lists cost megabytes
    on a long event-only tail)."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        buf = b""                        # unread bytes: the first (maybe partial) line and before
        while pos > 0:
            step = min(chunk, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
            end = len(buf)
            i = buf.rfind(b"\n", 0, end)
            while i >= 0:
                line = buf[i + 1:end]
                if line.strip():
                    yield line.decode(errors="replace")
                end = i
                i = buf.rfind(b"\n", 0, end)
            buf = buf[:end]
            chunk = min(chunk * 2, max_chunk)
        if buf.strip():
            yield buf.decode(errors="replace")


@dataclass
class RvfiTail:
    retired: list[dict] = field(default_factory=list)   # last N retirements, oldest first
    traps: list[dict] = field(default_factory=list)     # the most recent trap events (at most 2n+16), oldest first
    total: int | None = None                            # `order` of the last retirement + 1


def read_rvfi_tail(path: str, n: int = 64) -> RvfiTail:
    t = RvfiTail()
    # Read back until `n` retirements are found (and at least the last 2n+16 lines, for the trap events
    # near them) or the file starts: trailing events (irq levels, ...) can follow the last retirement
    # by any number of lines, and an event-only tail is no proof that nothing retired. Only the most
    # recent 2n+16 traps are kept while scanning (review 5: a trap-only tail kept them all).
    seen = 0
    max_traps = n * 2 + 16
    for line in reverse_lines(path):
        if len(t.retired) >= n and seen >= n * 2 + 16:
            break
        seen += 1
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(r, dict) or "schema" in r:
            continue
        ev = r.get("event")
        if ev == "trap":
            if len(t.traps) < max_traps:     # read last first: the first ones found are the newest
                t.traps.append(r)
        elif ev is None and "pc" in r and len(t.retired) < n:
            t.retired.append(r)
    t.retired.reverse()
    t.traps.reverse()
    if t.retired:
        t.total = int(t.retired[-1].get("order", -1)) + 1
    return t


def hexint(v) -> int | None:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(str(v), 16) if str(v).startswith("0x") else int(v)
    except ValueError:
        return None


def loop_info(retired: list[dict], max_pcs: int = 16) -> dict | None:
    """If the most recent retirements keep revisiting a small set of pcs, describe that loop: the
    smallest k <= `max_pcs` such that the longest suffix with k distinct pcs is >= 3k long."""
    if len(retired) < 12:
        return None
    pcs_rev = [r["pc"] for r in reversed(retired)]
    for k in range(1, max_pcs + 1):
        seen: set = set()
        n = 0
        for pc in pcs_rev:
            if pc not in seen and len(seen) == k:
                break
            seen.add(pc)
            n += 1
        if n >= 3 * k and len(seen) == k:
            vals = [hexint(p) for p in seen]
            return {"distinct_pcs": k, "pc_lo": hex(min(vals)), "pc_hi": hex(max(vals)), "of": n}
    return None


@dataclass
class InFlight:
    id: str
    label: str        # Kanata label type 0 (the left pane: pc and disassembly)
    stage: str
    since: int        # cycle the instruction entered `stage`
    born: int         # cycle it was fetched/created
    detail: str = ""  # Kanata label type 1 (hover text; core-specific, e.g. the ROB index)


def konata_inflight(path: str) -> tuple[list[InFlight], int]:
    """Instructions in the pipeline at the end of the log, oldest first, and that cycle.
    Uses the shared Kanata reader (`rvw.perf.kanata`: .gz logs, format checks)."""
    from ..perf import kanata
    tr = kanata.read(path)
    end = tr.end
    out = []
    for ins in sorted(tr.instructions.values(), key=lambda i: i.ordinal):
        if ins.start > end or (ins.end is not None and ins.end <= end):
            continue
        spans = [sp for sp in ins.spans if sp.start <= end]
        cur = spans[-1] if spans else None
        out.append(InFlight(ins.id, ins.labels.get("0", ""), cur.stage if cur else "", cur.start if cur else ins.start,
                            ins.start, ins.labels.get("1", "")))
    return out, end
