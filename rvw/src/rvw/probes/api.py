"""`rvw probes` operations shared by the CLI and the MCP tools."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import convert as cv
from .consumers import matrix
from .events import KINDS, read

PREFIX = "rvwprobe__"


def from_db(db) -> list[dict]:
    """Probes found in a design database by their wire names `rvwprobe__KIND__NAME__FIELD`.

    The database has no probe meta (stage names, selectors), so `meta` is None. The design
    database must be built from an elaboration with probes enabled."""
    con = sqlite3.connect(f"file:{Path(db)}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT s.name, s.width, c.path FROM signals s JOIN components c ON c.id = s.component_id "
            "WHERE s.name LIKE 'rvwprobe\\_\\_%' ESCAPE '\\' ORDER BY s.id").fetchall()
    finally:
        con.close()
    probes: dict[tuple, dict] = {}
    for name, width, component in rows:
        parts = name.split("__")
        if len(parts) != 4 or parts[1] not in KINDS:
            continue
        _, kind, pname, fname = parts
        p = probes.setdefault((component, kind, pname), {"kind": kind, "name": pname, "component": component,
                                                          "fields": [], "widths": {}, "meta": None})
        if fname != "valid":
            p["fields"].append(fname)
            p["widths"][fname] = width
    return list(probes.values())


def from_events(path) -> list[dict]:
    s = read(path)
    return [{"kind": p.kind, "name": p.name, "fields": p.names, "widths": dict(p.fields), "meta": p.meta}
            for p in s.probes]


def report(db=None, events=None) -> dict:
    """List probes and the consumer matrix: which tools each probe enables, which are missing."""
    if (db is None) == (events is None):
        raise ValueError("give exactly one of db or events")
    probes = from_db(db) if db is not None else from_events(events)
    rows = matrix(probes)
    out = {"schema": "rvw.probes-report/1", "source": {"db": str(db)} if db else {"events": str(events)},
           "probes": probes, "consumers": rows,
           "enabled": [r["consumer"] for r in rows if r["status"] == "enabled"],
           "missing": [r["consumer"] for r in rows if r["status"] != "enabled"]}
    if not probes:
        out["note"] = "no probes found; elaborate with probes enabled (C1 --probes)"
    return out


def run_convert(events, to, out, c2=None, c1=None, probe=None, roi=None) -> dict:
    s = read(events)
    if to not in cv.CONVERTERS:
        raise ValueError(f"unknown target {to}; choose from {', '.join(sorted(cv.CONVERTERS))}")
    def need(x, name):
        if x is None:
            raise ValueError(f"--to {to} needs {name}")
        return x
    if to == "bp-events":
        return cv.bp_events(s, need(c2, "--c2"), out, probe=probe, roi=roi)
    if to == "kanata":
        return cv.kanata(s, out)
    if to == "cache":
        return cv.cache(s, out)
    if to == "mmu":
        return cv.mmu(s, out, c2)
    if to == "counts":
        return cv.counts(s, out, need(c1, "--c1"), need(c2, "--c2"))
    if to == "hpm":
        return cv.hpm(s, out)
    if to == "etrace-ingress":
        return cv.etrace_ingress(s, out, probe=probe)
    if to in ("bus", "csr-writes"):
        from . import checks
        run = checks.bus if to == "bus" else checks.csr_writes
        return run(s, need(c2, "--c2"), out, probe=probe)
    return cv.interrupts(s, need(c2, "--c2"), out)


def summary(events) -> dict:
    return cv.summary(read(events))
