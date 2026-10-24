"""Condense a SpinalTrace dynamic PDG (dynpdg.json) into the source statements closest to the traced
value: breadth-first over dependency edges from the newest vertex, one row per statement at its
smallest distance, with its value then and its module."""
from __future__ import annotations

import json
from collections import deque


def digest(path: str, limit: int = 30, criterion: str | None = None) -> list[dict]:
    with open(path) as f:
        d = json.load(f)
    vs, es = d.get("vertices", []), d.get("edges", [])
    if not vs:
        return []
    # The order of vertices and edges in dynpdg.json is not stable between runs (hash sets in
    # spinaltrace-rs); order everything by content so the digest is.
    def key(i):
        v = vs[i]
        return (-v["timestamp"], v.get("file", ""), v.get("line", 0), v.get("name", ""), str(v.get("sim_data")))

    out_edges: dict[int, list[dict]] = {}
    for e in es:
        out_edges.setdefault(e["from"], []).append(e)
    for lst in out_edges.values():
        lst.sort(key=lambda e: (key(e["to"]), e.get("kind", "")))
    tmax = max(v["timestamp"] for v in vs)
    roots = sorted((i for i, v in enumerate(vs) if v["timestamp"] == tmax), key=key)
    if criterion and criterion.startswith("line:"):
        _, f, l = criterion.split(":", 2)
        own = [i for i in roots if vs[i]["file"].rsplit("/", 1)[-1] == f and str(vs[i]["line"]) == l]
        roots = own or roots
    dist = {i: 0 for i in roots}
    via: dict[int, str] = {}
    q = deque(roots)
    while q:
        i = q.popleft()
        for e in out_edges.get(i, []):
            j = e["to"]
            if j not in dist:
                dist[j] = dist[i] + 1
                via[j] = e["kind"].lower()
                q.append(j)
    rows: dict[tuple, dict] = {}
    for i, k in sorted(dist.items(), key=lambda x: (x[1], key(x[0]))):
        v = vs[i]
        key = (v["file"], v["line"], v["name"])
        if key in rows:
            rows[key]["hits"] += 1
            continue
        rows[key] = {"depth": k, "t": v["timestamp"] - tmax, "where": f"{v['file'].rsplit('/', 1)[-1]}:{v['line']}",
                     "statement": v["name"], "value": v.get("sim_data"), "via": via.get(i, "root"),
                     "module": ".".join(v.get("module_path") or []), "hits": 1}
    return list(rows.values())[:limit]


def render_md(rows: list[dict]) -> str:
    L = ["| depth | cycle | where | statement | value | edge | module |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['depth']} | {r['t']:+d} | {r['where']} | `{r['statement']}` | {r['value'] or ''} | "
                 f"{r['via']} | {r['module']} |")
    return "\n".join(L)
