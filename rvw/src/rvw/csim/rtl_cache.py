"""Compare a cache model with RTL cache probe events, access by access.

The model (`memory.l1d` or `memory.l1i` of a study, through `rvw.csim.lib`) runs on the C2
trace of the same run: one data access per retired load/store/AMO, or one fetch per retired
instruction (FENCE.I invalidates the model I-cache). The RTL side is the `access` events of one
cache probe (`Probe.cacheAccess(cache, "access", ..., hit = ...)`) in a `rvw.probe-events/1`
stream, one per retired access in retirement order. The k-th RTL access is paired with the
k-th model access; the pair must name the same line, else the comparison is `inconclusive`.
Agreement is a measured model gap, never a correctness or fidelity verdict.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from . import config as cfg

REPORT = "rvw.csim-cache-compare/1"
FENCE_I = (0x707F, 0x100F)


def _int(v) -> int:
    return v if isinstance(v, int) else int(str(v), 0)


def _rtl(events, cache: str):
    from rvw.probes.events import read
    stream = read(events)
    access = [p for p in stream.of_kind("cache") if p.meta.get("cache") == cache and p.meta.get("event") == "access"]
    if not access:
        names = sorted({p.meta.get("cache") for p in stream.of_kind("cache")})
        raise ValueError(f"no access probe for cache {cache!r} (caches: {', '.join(map(str, names)) or 'none'})")
    ids = {p.id for p in access}
    if any("hit" not in dict(p.fields) for p in access):
        raise ValueError(f"the {cache} access probe has no hit field")
    rows, fills, evicts = [], 0, 0
    for cycle, p, v in stream.events("cache"):
        if p.id in ids:
            rows.append((cycle, v["address"], bool(v["hit"]), bool(v.get("write", 0))))
        elif p.meta.get("cache") == cache:
            fills += p.meta.get("event") == "fill"
            evicts += p.meta.get("event") == "evict"
    return stream, rows, fills, evicts


def _c2(path):
    header, recs, end = None, [], None
    with Path(path).open() as f:
        header = json.loads(f.readline())
        if not str(header.get("schema", "")).startswith("rvw.rvfi/"):
            raise ValueError("not a C2 trace")
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get("event") == "end":
                    end = r
                elif "event" not in r:
                    recs.append(r)
    return header, recs, end


def model_accesses(recs: list[dict], fetch: bool):
    """(ordinal, order, pc, address, store, flush_after, cycle) per model access, from C2 records."""
    out = []
    for n, r in enumerate(recs, 1):
        if r.get("trap"):
            continue
        pc, insn = _int(r["pc"]), _int(r["insn"])
        if fetch:
            out.append((n, r["order"], pc, pc, False, insn & FENCE_I[0] == FENCE_I[1], int(r.get("cycle", -1))))
            continue
        rmask, wmask = _int(r.get("mem_rmask", 0)), _int(r.get("mem_wmask", 0))
        if rmask or wmask:
            # An AMO reads and writes: it is looked up as a load (it allocates).
            out.append((n, r["order"], pc, _int(r["mem_addr"]), not rmask, False, int(r.get("cycle", -1))))
    return out


def compare(study_path, c2_path, events_path, cache: str = "dcache", level: str | None = None,
            top: int = 20, trace_out=None, tail_cycles: int = 4) -> dict:
    """`tail_cycles`: retired accesses with no RTL event are an `unsampled_tail` (not a reason)
    when they are the last ones and retired within this many cycles of the probe stream's end
    (a probe sampled later than the C2 stamp misses commits once the run stops)."""
    from .lib import Components
    level = level or ("l1i" if cache.startswith("i") else "l1d")
    if level not in ("l1i", "l1d"):
        raise ValueError("level must be l1i or l1d")
    data = cfg.load(study_path)
    mem = data.get("memory") or {}
    if level not in mem:
        raise ValueError(f"the study has no memory.{level}")
    line_bits = (int(mem[level].get("line_bytes", 64)) - 1).bit_length()
    fetch = level == "l1i"
    stream, rtl, fills, evicts = _rtl(events_path, cache)
    header, recs, c2_end = _c2(c2_path)
    reasons: list[str] = []
    a, b = stream.identity.get("elf_sha256"), header.get("elf_sha256")
    if not a or not b:
        reasons.append("missing ELF identity on the trace or the events")
    elif a != b:
        reasons.append("ELF identity differs between trace and events")
    if c2_end is None:
        reasons.append("incomplete C2 trace (no end record)")
    if stream.end is None:
        reasons.append("incomplete probe stream (no end record)")
    model = model_accesses(recs, fetch)
    counts = defaultdict(int)
    per_pc: dict[int, dict] = defaultdict(lambda: defaultdict(int))
    first: list[dict] = []
    misaligned = None
    rows = []
    with Components({"memory": mem}) as comp:
        for k, (m, r) in enumerate(zip(model, rtl)):
            ordinal, order, pc, address, store, flush, _ = m
            cycle, raddress, rhit, rwrite = r
            if raddress != address or rwrite != store:
                misaligned = {"index": k, "order": order, "pc": hex(pc), "model_line": hex(address >> line_bits << line_bits),
                              "rtl_line": hex(raddress >> line_bits << line_bits), "rtl_cycle": cycle}
                break
            _, mhit = comp.access_hit(ordinal, pc, address, store=store, fetch=fetch)
            if flush:
                comp.flush(fetch=True)
            kind = ("both_hit" if mhit else "rtl_hit_model_miss") if rhit else ("model_hit_rtl_miss" if mhit else "both_miss")
            counts[kind] += 1
            counts["stores" if store else "loads"] += 1
            if rhit != mhit:
                p = per_pc[pc]
                p["disagreements"] += 1
                p["rtl_misses"] += not rhit
                p["model_misses"] += not mhit
                if len(first) < top:
                    first.append({"index": k, "order": order, "pc": hex(pc), "address": hex(address), "store": store,
                                  "rtl_hit": rhit, "model_hit": mhit, "rtl_cycle": cycle})
            rows.append((ordinal, pc, raddress, store))
        stats = comp.stats(len(recs))
    if misaligned:
        reasons.append(f"access {misaligned['index']} differs in address or write direction between RTL and trace")
    tail = model[len(rtl):]
    end_cycle = int((stream.end or {}).get("cycles", -1))
    unsampled = len(tail) if tail and not misaligned and all(0 <= end_cycle - m[6] <= tail_cycles for m in tail) else 0
    if len(model) != len(rtl):
        reasons.append(f"{len(rtl)} RTL access events for {len(model)} retired accesses in the trace")
    n = sum(counts[k] for k in ("both_hit", "both_miss", "rtl_hit_model_miss", "model_hit_rtl_miss"))
    if not n:
        reasons.append("no comparable accesses")
    rtl_miss = counts["both_miss"] + counts["model_hit_rtl_miss"]
    model_miss = counts["both_miss"] + counts["rtl_hit_model_miss"]
    instructions = len(recs)
    summary = {"accesses": n, **{k: counts[k] for k in ("both_hit", "both_miss", "rtl_hit_model_miss", "model_hit_rtl_miss",
                                                       "loads", "stores")}}
    if n:
        summary.update({"agreement": (counts["both_hit"] + counts["both_miss"]) / n,
                        "rtl_miss_rate": rtl_miss / n, "model_miss_rate": model_miss / n,
                        "miss_rate_error": (model_miss - rtl_miss) / n,
                        "rtl_mpki": 1000 * rtl_miss / instructions, "model_mpki": 1000 * model_miss / instructions})
    if trace_out and rows:
        with Path(trace_out).open("x") as f:
            f.write("rvw.csim-trace/1\n")
            f.write(f"# source=rtl-cache-probe cache={cache} elf={header.get('elf', '')}\n")
            for ordinal, pc, address, store in rows:
                f.write(f"{'S' if store else 'L'} {ordinal} {pc:x} {address:x} 4\n")
            f.write(f"END {instructions}\n")
    worst = sorted(({"pc": hex(pc), **dict(v)} for pc, v in per_pc.items()), key=lambda r: -r["disagreements"])[:top]
    return {"schema": REPORT, "status": "inconclusive" if reasons else "compared", "reasons": reasons,
            "cache": cache, "level": level, "study": data.get("name"), "study_sha256": cfg.digest(data),
            "trace": str(c2_path), "events": str(events_path), "instructions": instructions,
            "rtl_events": {"access": len(rtl), "fill": fills, "evict": evicts},
            "model_accesses": len(model), "unsampled_tail": unsampled, "summary": summary, "misaligned": misaligned,
            "first_disagreements": first, "per_pc": worst,
            "model_stats": (stats.get("memory") or {}).get(level), "trace_out": str(trace_out) if trace_out else None,
            "note": "Agreement is a measured model gap, not an RTL correctness or fidelity verdict."}
