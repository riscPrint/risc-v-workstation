"""Converters from `rvw.probe-events/1` into the formats the consumer tools already read.

Each converter refuses input that it cannot place exactly (for example branch events that do
not line up with C2 retirements). No converter fills in an event that the core did not emit.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from rvw.csim.traces import branch_kind

from .events import Stream

CACHE_KINDS = {"fill", "denied", "read", "store", "evict", "invalidate"}
INGRESS = ['itype_0', 'cause', 'tval', 'priv', 'iaddr_0', 'context', 'ctype', 'iretire_0', 'ilastsize_0']


def _hex(v: int) -> str:
    return f"0x{v:x}"


def _int(v) -> int:
    return v if isinstance(v, int) else int(v, 16) if str(v).startswith("0x") else int(v)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_c2(path) -> tuple[dict, list[dict], list[dict]]:
    """(header, retirement records, event records) of a one-hart C2 trace."""
    with Path(path).open() as f:
        header = json.loads(f.readline())
        if not str(header.get("schema", "")).startswith("rvw.rvfi/"):
            raise ValueError("not a C2 trace")
        recs, evs = [], []
        for line in f:
            if line.strip():
                r = json.loads(line)
                (evs if "event" in r else recs).append(r)
    return header, recs, evs


def _check_identity(stream: Stream, c2_header: dict) -> None:
    a, b = stream.identity.get("elf_sha256"), c2_header.get("elf_sha256")
    if a and b and a != b:
        raise ValueError("probe stream and C2 trace are for different ELF files")


def _one(stream: Stream, kind: str, name: str | None):
    probes = [p for p in stream.of_kind(kind) if name is None or p.name == name]
    if len(probes) != 1:
        raise ValueError(f"expected one {kind} probe{' named ' + name if name else ''}, found {len(probes)}"
                         + ("; select one with --probe" if len(probes) > 1 else ""))
    return probes[0]


def bp_events(stream: Stream, c2_path, out, probe: str | None = None, roi: tuple[int, int] | None = None) -> dict:
    """`rvw.bp-events/1`: one row per retired branch, aligned 1:1 with C2 retirements in order.

    The probe must fire once per retired branch of the kinds in its `covers` meta. A count or
    PC difference means the probe also saw speculative branches (or missed some): refused."""
    p = _one(stream, "branch", probe)
    header, recs, _ = read_c2(c2_path)
    _check_identity(stream, header)
    covers = set(p.meta.get("covers", "cond,jump,ijump,call,icall,ret").split(","))
    xlen = int(header.get("xlen", 64))
    branches = []
    for r in recs:
        if r.get("trap"):
            continue
        insn, pc, nxt = _int(r["insn"]), _int(r["pc"]), _int(r["pc_next"])
        kind = branch_kind(insn, int(r.get("rd", 0)), xlen)
        if kind in covers:
            length = 4 if insn & 3 == 3 else 2
            branches.append((int(r["order"]), pc, kind, nxt != pc + length if kind == "cond" else True))
    events = [v for _, q, v in stream.events("branch") if q.id == p.id]
    if len(events) != len(branches):
        raise ValueError(f"{len(events)} branch events but {len(branches)} retired branches in C2; "
                         "probe the commit point so that every event belongs to one retirement")
    semantics = p.meta.get("semantics")
    if semantics not in ("first-prediction", "final-prediction"):
        raise ValueError("branch probe has no first-prediction/final-prediction semantics")
    head = {"schema": "rvw.bp-events/1", "elf_sha256": header.get("elf_sha256") or stream.identity.get("elf_sha256"),
            "hart": 0, "counter_semantics": semantics, "source": "rvw.probe-events/1", "probe": p.name}
    if roi:
        head["roi"] = {"start_order": roi[0], "end_order": roi[1]}
    stats = defaultdict(int)
    with Path(out).open("x") as f:
        f.write(json.dumps(head) + "\n")
        for (order, pc, kind, taken), e in zip(branches, events):
            if e["pc"] != pc:
                raise ValueError(f"branch event pc {_hex(e['pc'])} does not match C2 order {order} pc {_hex(pc)}")
            if bool(e["taken"]) != taken:
                raise ValueError(f"branch event at order {order} disagrees with C2 on the taken outcome")
            row = {"order": order, "pc": _hex(pc), "kind": kind, "taken": taken, "target": _hex(e["target"])}
            if "predicted_taken" in e:
                row["predicted_taken"] = bool(e["predicted_taken"])
                stats["direction_misses"] += kind == "cond" and row["predicted_taken"] != taken
            if "btb_hit" in e:
                row["btb_hit"] = bool(e["btb_hit"])
            if "predicted_target" in e:
                row["predicted_target"] = _hex(e["predicted_target"])
            stats[kind] += 1
            f.write(json.dumps(row) + "\n")
    return {"format": "rvw.bp-events/1", "rows": len(branches), "kinds": dict(stats)}


def kanata(stream: Stream, out) -> dict:
    """Kanata 0004 from stage occupancy, retire, flush and stall probes.

    A probe ID names one instruction from its first stage event until its retire or flush;
    after that the same ID starts a new instruction. Instructions left open at the end stay open.
    When a stage probe has meta `first`, only such stages start instructions; other events for an
    ID that is not live are counted as `orphan_events`. A flush with meta `range: younger` closes
    every live instruction that started after the latest instruction with its ID (and that one
    too when its `inclusive` value is set)."""
    live: dict[int, str] = {}
    latest: dict[int, int] = {}
    current: dict[str, tuple[str, str]] = {}
    order = {"stage": 0, "stall": 1, "branch": 2, "retire": 3, "flush": 4}
    gated = any(p.meta.get("first") == "true" for p in stream.of_kind("stage"))
    by_cycle = defaultdict(list)
    for cycle, p, v in stream.events("stage", "stall", "branch", "retire", "flush"):
        if p.kind == "branch" and ("id" not in v or "predicted_taken" not in v):
            continue  # a prediction record needs the instruction ID and the prediction
        by_cycle[cycle].append((order[p.kind], p.id, p, v))
    serial = retired = flushed = stalls = predictions = orphans = unanchored = stale = 0
    lines = ["Kanata\t0004"]
    last = None
    bounds = stream.end or {}
    first_cycle, last_cycle = bounds.get("first_cycle"), bounds.get("last_cycle")
    if first_cycle is not None or last_cycle is not None:
        if type(first_cycle) is not int or type(last_cycle) is not int or not 0 <= first_cycle <= last_cycle:
            raise ValueError("invalid probe sampling bounds")
        if by_cycle and (min(by_cycle) < first_cycle or max(by_cycle) > last_cycle):
            raise ValueError("events outside probe sampling bounds")
        lines.append(f"C=\t{first_cycle}")
        last = first_cycle

    def start(pid_value: int, pc: int | None) -> str:
        nonlocal serial
        key = str(serial)
        latest[pid_value] = serial
        serial += 1
        live[pid_value] = key
        lines.append(f"I\t{key}\t{key}\t0")
        if pc is not None:
            lines.append(f"L\t{key}\t0\t{pc:x}: ")
        return key

    def close(ident: int, kind: int) -> None:
        nonlocal retired, flushed
        key = live.pop(ident)
        lines.append(f"R\t{key}\t{retired if kind == 0 else flushed}\t{kind}")
        retired += kind == 0
        flushed += kind == 1
        current.pop(key, None)

    for cycle in sorted(by_cycle):
        lines.append(f"C=\t{cycle}" if last is None else f"C\t{cycle - last}")
        last = cycle
        for _, _, p, v in sorted(by_cycle[cycle], key=lambda t: (t[0], t[1])):
            if p.kind == "stall":
                lines.append(f"#rvw\t1\tstall\t{p.meta['scope']}\t{p.meta['cause']}\t{p.meta.get('evidence', 'measured')}")
                stalls += 1
                continue
            ident = v["id"]
            if p.kind == "flush" and p.meta.get("range") == "younger":
                anchor = latest.get(ident)
                if anchor is None:
                    unanchored += 1
                    continue
                victims = [i for i, k in live.items() if int(k) > anchor or (int(k) == anchor and v.get("inclusive"))]
                for i in sorted(victims, key=lambda i: int(live[i])):
                    close(i, 1)
                continue
            if p.kind == "branch":
                key = live.get(ident)
                if key is None:
                    raise ValueError(f"branch probe {p.name}: ID {ident} at cycle {cycle} is not a live instruction")
                way = ("not_taken", "taken")
                lines.append(f"#rvw\t1\tprediction\t{key}\t{p.name}\tdirection\t{way[v['predicted_taken']]}"
                             f"\t{way[v['taken']]}\t?\t?\t?\t?\t?")
                predictions += 1
                continue
            key = live.get(ident)
            if key is None:
                if gated and not (p.kind == "stage" and p.meta.get("first") == "true"):
                    orphans += 1
                    continue
                key = start(ident, v.get("pc"))
            elif (gated and p.kind == "stage" and p.meta.get("first") == "true"
                  and current.get(key, ("", ""))[1] != p.meta.get("stage", p.name)):
                # A reused ID enters again: its older instruction ended without a probe event.
                close(ident, 1)
                stale += 1
                key = start(ident, v.get("pc"))
            if p.kind == "stage":
                lane, name = p.meta.get("lane", "0"), p.meta.get("stage", p.name)
                prev = current.get(key)
                if prev != (lane, name):
                    if prev and prev[0] == lane:
                        lines.append(f"E\t{key}\t{prev[0]}\t{prev[1]}")
                    lines.append(f"S\t{key}\t{lane}\t{name}")
                    current[key] = (lane, name)
            else:
                close(ident, 0 if p.kind == "retire" else 1)
    if last_cycle is not None:
        lines.append(f"C=\t{last_cycle}")
    with Path(out).open("x") as f:
        f.write("\n".join(lines) + "\n")
    result = {"format": "Kanata 0004", "instructions": serial, "retired": retired, "flushed": flushed,
              "stall_samples": stalls, "predictions": predictions, "open": len(live)}
    if gated:
        result["orphan_events"] = orphans
        result["stale_closed"] = stale
    if unanchored:
        result["unanchored_flushes"] = unanchored
    return result


def _bytes(value: int, width: int) -> str:
    n = max(1, width // 8)
    return value.to_bytes(n, "little").hex()


def cache(stream: Stream, out) -> dict:
    """Cache observer events (RiscvSim `CacheEventObserver`): one JSON object per line.

    `event` is `CACHE.EVENT`; `names` maps it to an observer kind when the probe's event word
    is one (fill, denied, read, store, evict, invalidate), else null for the project to map."""
    counts, names = defaultdict(int), {}
    with Path(out).open("x") as f:
        for cycle, p, v in stream.events("cache"):
            name = f"{p.meta['cache']}.{p.meta['event']}"
            names[name] = p.meta["event"] if p.meta["event"] in CACHE_KINDS else None
            row = {"cycle": cycle, "hart": 0, "event": name, "physical_address": _hex(v["address"])}
            widths = dict(p.fields)
            if "data" in v:
                row["bytes"] = _bytes(v["data"], widths["data"])
            if "mask" in v:
                row["mask"] = _hex(v["mask"])
            for flag in ("hit", "write"):
                if flag in v:
                    row[flag] = bool(v[flag])
            if "way" in v:
                row["way"] = v["way"]
            counts[name] += 1
            if "hit" in v:
                counts[f"{name}.{'hit' if v['hit'] else 'miss'}"] += 1
            f.write(json.dumps(row) + "\n")
    return {"format": "cache observer events", "names": names, "counts": dict(counts)}


def mmu(stream: Stream, out, c2_path=None) -> dict:
    """`rvw.mmu-observations/1` rows: tlb_fill/hit/miss/invalidate and walk_request/response."""
    identity = stream.identity
    if c2_path:
        header, _, _ = read_c2(c2_path)
        _check_identity(stream, header)
        identity = header
    counts = defaultdict(int)
    with Path(out).open("x") as f:
        f.write(json.dumps({"schema": "rvw.mmu-observations/1", "identity": identity,
                            "source": "rvw.probe-events/1"}) + "\n")
        for cycle, p, v in stream.events("tlb", "walk"):
            if p.kind == "walk" and p.meta.get("event") == "result":
                continue  # walk results feed `--to mmu-walks`
            if p.kind == "tlb":
                kind = "tlb_" + p.meta["event"]
                row = {"cycle": cycle, "kind": kind, "hart": 0}
                for k in ("va", "pa", "pte_address", "pte"):
                    if k in v:
                        row[k] = _hex(v[k])
                for k in ("entry", "size", "asid"):
                    if k in v:
                        row[k] = v[k]
                if "global" in v:
                    row["global"] = bool(v["global"])
                if kind == "tlb_invalidate":
                    row.setdefault("va", None)
                    row.setdefault("asid", None)
            else:
                kind = "walk_" + p.meta["event"]
                row = {"cycle": cycle, "kind": kind, "address": _hex(v["address"])}
                if kind == "walk_request":
                    row["command"] = "read"
                if "data" in v:
                    row["data"] = _hex(v["data"])
                if "level" in v:
                    row["level"] = v["level"]
                if "fault" in v:
                    row["fault"] = bool(v["fault"])
            counts[kind] += 1
            f.write(json.dumps(row) + "\n")
    return {"format": "rvw.mmu-observations/1", "counts": dict(counts)}


def counts(stream: Stream, out, c1_path, c2_path) -> dict:
    """RTL event counts for `rvw arch ooo-calibrate`, bound to the run's C1 and C2 files."""
    if stream.end is None:
        raise ValueError("probe stream has no end record (incomplete run); counters are not totals")
    if not stream.of_kind("counter"):
        raise ValueError("probe stream has no counter probes")
    data = {"c1_sha256": _sha(c1_path), "trace_sha256": _sha(c2_path), "counts": stream.counters,
            "cycles": int(stream.end.get("cycles", 0)), "source": "rvw.probe-events/1"}
    with Path(out).open("x") as f:
        json.dump(data, f, indent=1)
    return {"format": "RTL event counts", "counts": data["counts"]}


def hpm(stream: Stream, out) -> dict:
    """`rvw.hpm-bindings/1`: mhpmevent selector values bound to counter probes and totals."""
    if stream.end is None:
        raise ValueError("probe stream has no end record (incomplete run)")
    bound = [p for p in stream.of_kind("counter") if "hpm" in p.meta]
    if not bound:
        raise ValueError("no counter probe declares an hpm selector")
    selectors = [int(p.meta["hpm"]) for p in bound]
    if len(set(selectors)) != len(selectors):
        raise ValueError("two counter probes bind the same hpm selector")
    totals = stream.counters
    data = {"schema": "rvw.hpm-bindings/1", "identity": stream.identity, "cycles": int(stream.end.get("cycles", 0)),
            "bindings": [{"selector": int(p.meta["hpm"]), "counter": p.name, "total": totals.get(p.name, 0)}
                         for p in sorted(bound, key=lambda p: int(p.meta["hpm"]))]}
    with Path(out).open("x") as f:
        json.dump(data, f, indent=1)
    return {"format": "rvw.hpm-bindings/1", "bindings": len(bound)}


def etrace_ingress(stream: Stream, out, probe: str | None = None) -> dict:
    """E-Trace encoder ingress CSV (the upstream reference encoder's input), from DUT signals."""
    p = _one(stream, "trace", probe)
    rows = 0
    with Path(out).open("x", newline="") as f:
        w = csv.writer(f)
        w.writerow(INGRESS)
        for _, q, v in stream.events("trace"):
            if q.id != p.id:
                continue
            w.writerow([v["itype"], v.get("cause", 0), v.get("tval", 0), v["priv"], f"{v['iaddr']:x}", 0, 0,
                        v["iretire"], v["ilastsize"]])
            rows += 1
    return {"format": "E-Trace encoder ingress CSV", "rows": rows}


def interrupts(stream: Stream, c2_path, out) -> dict:
    """`rvw.probe-interrupts/1`: interrupt-taken probe events against C2 interrupt trap events,
    in order, by cause. `consistent` only says the two independent sources agree."""
    header, _, evs = read_c2(c2_path)
    _check_identity(stream, header)
    if not stream.of_kind("interrupt"):
        raise ValueError("probe stream has no interrupt probes")
    probe = [(c, v["cause"], v["pc"]) for c, _, v in stream.events("interrupt")]
    c2 = [(e["cycle"], _int(e["cause"])) for e in evs if e.get("event") == "trap" and e.get("intr")]
    mismatches = []
    for n, (a, b) in enumerate(zip(probe, c2)):
        if a[1] != b[1]:
            mismatches.append({"index": n, "probe_cause": _hex(a[1]), "c2_cause": _hex(b[1]), "probe_cycle": a[0],
                               "c2_cycle": b[0]})
    if len(probe) != len(c2):
        mismatches.append({"count": {"probe": len(probe), "c2": len(c2)}})
    complete = bool(stream.end) and any(e.get("event") == "end" for e in evs)
    status = "mismatch" if mismatches else ("consistent" if complete and probe else "inconclusive")
    data = {"schema": "rvw.probe-interrupts/1", "status": status, "probe_events": len(probe), "c2_interrupts": len(c2),
            "mismatches": mismatches}
    if status == "inconclusive":
        data["reason"] = "no interrupts observed" if complete else "incomplete probe stream or C2 trace"
    with Path(out).open("x") as f:
        json.dump(data, f, indent=1)
    return data


def summary(stream: Stream) -> dict:
    counts = defaultdict(int)
    for _, pid, _ in stream.rows:
        counts[pid] += 1
    return {"schema": "rvw.probe-summary/1", "identity": stream.identity, "complete": stream.end is not None,
            "cycles": (stream.end or {}).get("cycles"),
            "probes": [{"id": p.id, "kind": p.kind, "name": p.name, "fields": p.names, "meta": p.meta,
                        "events": counts[p.id]} for p in stream.probes],
            "counters": stream.counters}


CONVERTERS = {"bp-events", "kanata", "cache", "mmu", "counts", "hpm", "etrace-ingress", "interrupts", "bus",
              "csr-writes", "mmu-walks", "fault-sites", "cache-check"}
