"""Converters that write records other tools read: C2 `mmu_walks` and `rvw fault` site lists.

`mmu-walks` groups each walker's `response` events up to its `result` event into one
`mmu_walk` record and attaches it to the first C2 retirement at or after the result cycle, in a
new copy of the trace. `rvw regress mmu report` then reads the records in order. The converter
does not decide which walks are architectural; the probe must emit only those.
"""
from __future__ import annotations

import json
from pathlib import Path

from rvw.regress.mmu_walk import validate_capture

from .convert import _check_identity
from .events import Stream

ACCESS = {0: "load", 1: "store", 2: "fetch"}
STATUS = {0: "success", 1: "page-fault", 2: "access-fault"}


def walk_records(stream: Stream) -> list[tuple[int, dict]]:
    """(result cycle, record) per completed walk, in stream order. `access_id` is sequential."""
    walks = [p for p in stream.of_kind("walk")]
    if not any(p.meta.get("event") == "result" for p in walks):
        raise ValueError("probe stream has no walk result probe (Probe.walkResult)")
    reads: dict[str, list[dict]] = {}
    out = []
    for cycle, p, v in stream.events("walk"):
        walker, event = p.meta.get("walker", p.name), p.meta.get("event")
        if event == "response":
            if "level" not in v:
                raise ValueError(f"walk probe {p.name}: a response needs a level field")
            fault = bool(v.get("fault", 0))
            read = {"level": v["level"], "address": v["address"], "fault": fault}
            if not fault:
                if "data" not in v:
                    raise ValueError(f"walk probe {p.name}: a response needs a data field")
                read["data"] = v["data"]
            reads.setdefault(walker, []).append(read)
        elif event == "result":
            if v["access"] not in ACCESS or v["status"] not in STATUS:
                raise ValueError(f"walk probe {p.name}: access {v['access']} or status {v['status']} is not a known code")
            record = {"kind": "mmu_walk", "access_id": len(out), "mode": p.meta.get("mode"),
                      "access": ACCESS[v["access"]], "va": v["va"], "root": v["root"],
                      "status": STATUS[v["status"]], "reads": reads.pop(walker, [])}
            if record["status"] == "success":
                record["pa"] = v["pa"]
            validate_capture(record)
            out.append((cycle, record))
    return out


def mmu_walks(stream: Stream, c2_path, out) -> dict:
    """Write a copy of the C2 trace with `mmu_walks` attached to retirements."""
    walks = walk_records(stream)
    attached = 0
    with Path(c2_path).open() as src, Path(out).open("x") as dst:
        header = json.loads(src.readline())
        if not str(header.get("schema", "")).startswith("rvw.rvfi/"):
            raise ValueError("not a C2 trace")
        _check_identity(stream, header)
        dst.write(json.dumps(header) + "\n")
        for line in src:
            if not line.strip():
                continue
            r = json.loads(line)
            if "event" not in r:
                if "mmu_walks" in r:
                    raise ValueError("the C2 trace already has mmu_walks records")
                if "cycle" not in r:
                    raise ValueError("C2 retirements need a cycle to place walk records")
                due = [w for c, w in walks[attached:] if c <= int(r["cycle"])]
                if due:
                    r["mmu_walks"] = due
                    attached += len(due)
            dst.write(json.dumps(r) + "\n")
    data = {"format": "C2 with mmu_walks", "walks": len(walks), "attached": attached,
            "unattached": len(walks) - attached}
    if attached != len(walks):
        data["status"] = "incomplete"
        data["reason"] = "walks completed after the last retirement have no record to go in"
    return data


def fault_sites(stream: Stream, out) -> dict:
    """`rvw fault plan --sites` input from the stream's fault probes (never sampled)."""
    probes = stream.of_kind("fault")
    if not probes:
        raise ValueError("probe stream has no fault site probes (Probe.faultSite)")
    sites = []
    for p in probes:
        if not p.meta.get("path"):
            raise ValueError(f"fault probe {p.name} has no register path (the collector predates fault paths)")
        sites.append({"path": p.meta["path"], "width": dict(p.fields)["value"], "clock_domain": None, "probe": p.name})
    data = {"source": "rvw.probe-events/1", "identity": stream.identity, "sites": sorted(sites, key=lambda s: s["path"]),
            "bits": sum(s["width"] for s in sites)}
    with Path(out).open("x") as f:
        json.dump(data, f, indent=1)
    return {"format": "rvw fault sites", "sites": len(sites), "bits": data["bits"]}
