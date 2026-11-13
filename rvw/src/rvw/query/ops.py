"""The `rvw query` operations. Each takes an open `DesignDB` and returns a JSON-able dict; the CLI and
the MCP tools are thin wrappers around these."""
from __future__ import annotations

import fnmatch
import gzip
import json
import os
import re
import tempfile
from collections import deque
from pathlib import Path

from rvw.common.capture import Capture, CaptureError

from .db import CAPTURE_SCHEMAS, STATE_SCHEMAS, DesignDB, QueryError, Signal, loc

# Strength of a dependency kind; a path through compiler temporaries gets the strongest kind on it
# (a data read that feeds a `when` condition is a control dependency of what the `when` assigns).
from .kinds import KIND_RANK
CONTROL = {"sel", "cond"}
# Filter relations, never a signal's role. A clock can also be read as ordinary data.
STATE_KINDS = {"reg", "mem", "mem_read"}
CLOCK_RELATIONS = {"clock", "reset", "clock_enable", "soft_reset"}


def _strongest(a: str, b: str) -> str:
    return a if KIND_RANK.get(a, 0) >= KIND_RANK.get(b, 0) else b


def cond_text(c: dict) -> str:
    k = c["kind"]
    if k == "when":
        return f"when({c['expr']})"
    if k == "else":
        return f"!({c['expr']})"
    if k == "case":
        return f"switch({c['expr']}) is({c['keys']})"
    return f"switch({c['expr']}) default"


def _assignment_rows(db: DesignDB, where: str, args) -> list[dict]:
    mask = "a.mask" if db.schema != "rvw.designdb/1" else "NULL"
    rows = db.q(f"SELECT a.id, a.target_id, a.component_id, a.kind, a.range, a.source, a.enable, a.cond_id, f.path, a.line, {mask} "
                f"FROM assignments a LEFT JOIN files f ON f.id = a.file_id WHERE {where} ORDER BY a.seq", args)
    out = []
    for r in rows:
        chain = db.cond_chain(r[7])
        d = {"id": r[0], "target": db.signal_by_id(r[1]).path, "kind": r[3]}
        if r[4]:
            d["range"] = r[4]
        d["source"] = r[5]
        if r[6]:
            d["enable"] = r[6]
        if r[10]:
            d["mask"] = r[10]
        if chain:
            d["condition"] = " && ".join(cond_text(c) for c in chain)
            d["conditions"] = [dict(c) for c in chain]
        comp = db.component(r[2])["path"]
        d["in_component"] = comp or db.top
        d["loc"] = loc(r[8], r[9])
        out.append(d)
    return out


# ---------------------------------------------------------------------------------------------- bundles
def interfaces(db: DesignDB, cid: int, comp_path: str, max_depth: int = 3) -> list[dict]:
    """Composite Data (Stream, Flow, Vec, bundles) of a component, up to `max_depth` levels below its roots."""
    rows = db.q("SELECT b.path, b.class_name, b.direction, b.signals, b.bits, f.path, b.line FROM bundles b "
                "LEFT JOIN files f ON f.id = b.file_id WHERE b.component_id = ? ORDER BY b.path", (cid,))
    out = []
    strip = len(comp_path) + 1 if comp_path else 0
    for p, cls, d, n, bits, f, line in rows:
        local = p[strip:]
        if local.count(".") >= max_depth:
            continue
        out.append({"interface": local, "type": cls, "direction": d, "signals": n, "bits": bits, "loc": loc(f, line)})
    return out


def bundle(db: DesignDB, name: str) -> dict | None:
    p = db.normalize(name)
    r = db.q("SELECT b.path, b.class_name, b.direction, b.signals, b.bits, f.path, b.line, c.path FROM bundles b "
             "JOIN components c ON c.id = b.component_id LEFT JOIN files f ON f.id = b.file_id WHERE b.path = ?", (p,))
    if not r:
        return None
    p, cls, d, n, bits, f, line, comp = r[0]
    return {"path": p, "type": cls, "direction": d, "signals": n, "bits": bits, "component": comp or db.top, "loc": loc(f, line)}


# ---------------------------------------------------------------------------------------------- where
def where(db: DesignDB, name: str) -> dict:
    sigs = db.resolve(name, allow_group=True)
    with tempfile.TemporaryDirectory(prefix="rvw-where-") as private:
        capture = Capture(Path(private) / "inputs")
        if len(sigs) > 1:
            d = {"query": name, "group": True, "count": len(sigs)}
            b = bundle(db, name)
            if b:
                d["bundle"] = b
            d["signals"] = [db.signal_json(s, brief=True) for s in sigs[:200]]
            entries = list(zip(sigs[:200], d["signals"]))
        else:
            d = {"query": name, "signal": db.signal_json(sigs[0])}
            entries = [(sigs[0], d["signal"])]
        for signal, entry in entries:
            if db.schema in CAPTURE_SCHEMAS and signal.file:
                try:
                    expected = _source_binding(db, signal.file)
                    item = capture.file(Path(signal.file))
                    if item.sha256 != expected:
                        raise QueryError(f"input_not_captured:source: {signal.file} differs from the database capture")
                    entry["source"] = _file_identity(item)
                except (CaptureError, QueryError) as exc:
                    entry["stored_loc"] = entry.pop("loc", None)
                    d.update(status="inconclusive", cause=str(exc))
        if len(sigs) == 1 and "verilog" in d["signal"]:
            try:
                v = _verilog_location(db, sigs[0], capture)
                if v:
                    d["signal"]["verilog"].update(v)
            except QueryError as exc:
                d.update(status="inconclusive", cause=str(exc))
        d["location_capture"] = capture.record()
        return d


def _file_identity(item) -> dict:
    return {"source": item.source, "resolved": item.resolved, "sha256": item.sha256, "size": item.size}


def _source_binding(db: DesignDB, path: str) -> str:
    """Match only stored lookup/resolved paths or an alias in a captured tree layout."""
    hashes = {row[0] for row in db.q("SELECT sha256 FROM input_files WHERE path=? OR resolved=?", (path, path))}
    # /18 tree members lost the root lookup alias. Retain navigation for those files
    # when the detached capture record proves the alias. Never resolve a live alias here.
    if not hashes:
        try:
            record = json.loads(db.meta.get('input_capture', '{}'))
            for tree in record.get('trees', []):
                try:
                    relative = Path(path).relative_to(tree['source'])
                    if '..' in relative.parts:
                        continue
                except ValueError:
                    continue
                for item in tree['files']:
                    if Path(item['copy']).relative_to(tree['copy']) == relative:
                        hashes.add(item['sha256'])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise QueryError(f"input_not_captured:source: {path} has an invalid content binding") from exc
    if len(hashes) != 1:
        raise QueryError(f"input_not_captured:source: {path} has no unique content binding")
    return hashes.pop()


def _verilog_location(db: DesignDB, s: Signal, capture: Capture) -> dict | None:
    """Declaration line from captured RTL that matches the database's content binding."""
    if db.schema not in CAPTURE_SCHEMAS:
        return None
    comp = db.component(s.component_id)
    module_re = re.compile(rf"^\s*module\s+{re.escape(comp['module'])}\b")
    decl_re = re.compile(rf"^\s*(input|output|inout|wire|reg|logic)\b[^;]*?\b{re.escape(s.name)}\b")
    if s.kind == "mem":
        decl_re = re.compile(rf"^\s*reg\b[^;]*\b{re.escape(s.name)}\b")
    inputs = []
    for (path,) in db.q("SELECT path FROM rtl_files"):
        if Path(path).suffix not in (".v", ".sv"):
            continue
        try:
            item = capture.file(Path(path))
        except CaptureError as exc:
            raise QueryError(str(exc)) from exc
        expected = db.q("SELECT sha256 FROM input_files WHERE path=?", (path,))
        if not expected or item.sha256 != expected[0][0]:
            raise QueryError(f"input_not_captured:rtl: {path} differs from the database capture")
        inputs.append(item)
    for item in inputs:
        in_module = False
        for i, line in enumerate(item.copy.read_text(errors="replace").splitlines(), 1):
            if not in_module:
                in_module = bool(module_re.match(line))
            elif line.lstrip().startswith("endmodule"):
                break
            elif decl_re.match(line):
                return {"loc": f"{item.source}:{i}", **_file_identity(item)}
    return None


# ---------------------------------------------------------------------------------------------- drivers
def drivers(db: DesignDB, name: str) -> dict:
    s = db.resolve_one(name)
    d = {"signal": db.signal_json(s)}
    assigns = _assignment_rows(db, "a.target_id = ?", (s.id,))
    if s.is_reg:
        cd = db.clock_domain(s.clock_domain_id) or {}
        d["register"] = {"clock": cd.get("clock"), "edge": cd.get("edge"),
                         "reset": ({"signal": cd.get("reset"), "kind": cd.get("reset_kind"),
                                    "active": cd.get("reset_active"), "value": s.reset_value}
                                   if s.reset_value is not None and cd.get("reset") else None),
                         "clock_enable": cd.get("clock_enable")}
        if s.reset_value is None:
            d["register"]["note"] = "no reset value: the register is not reset"
    d["assignments"] = [a for a in assigns if a["kind"] != "init"]
    if len(d["assignments"]) > 1:
        d["note"] = "assignments are listed in elaboration order; a later one wins when its condition holds"
    comp = db.component(s.component_id)
    if not d["assignments"]:
        if s.direction == "in" and comp["parent_id"] is None:
            d["origin"] = "primary input of the toplevel"
        elif s.clock_role:
            d["origin"] = f"{s.clock_role} of a clock domain"
        elif comp["blackbox"] and s.direction == "out":
            d["origin"] = f"output of BlackBox {comp['module']} (opaque: depends on all its inputs and inouts)"
        elif comp["blackbox"] and s.direction == "inout":
            d["origin"] = f"inout of BlackBox {comp['module']} (opaque: depends on all its other inputs and inouts)"
        elif s.kind == "mem_read":
            d["origin"] = "synchronous memory read port state (database node)"
        elif s.kind == "mem":
            d["origin"] = "memory without write ports (ROM or initialized)"
        else:
            d["origin"] = "no assignment (undriven, or driven only through a pruned path)"
    if s.kind == "mem":
        d["memory"] = _memory(db, s)
    d["read_signals"] = _neighbours(db, s.id, "in")
    return d


def _memory(db: DesignDB, s: Signal) -> dict | None:
    init = "init_sha256, init_words" if db.schema != "rvw.designdb/1" else "NULL, NULL"
    r = db.q(f"SELECT id, width, depth, technology, {init} FROM memories WHERE signal_id = ?", (s.id,))
    if not r:
        return None
    mid, width, depth, tech, init_sha, init_words = r[0]
    output_id = "p.output_id" if db.schema in STATE_SCHEMAS else "NULL"
    ports = db.q("SELECT p.kind, p.address, p.data, p.enable, p.write_enable, p.mask, p.clock_domain_id, p.cond_id, f.path, p.line, " + output_id + " "
                 "FROM mem_ports p LEFT JOIN files f ON f.id = p.file_id WHERE p.memory_id = ? ORDER BY p.id", (mid,))
    out = []
    for k, a, data, en, wen, mask, cd, cond, f, line, output in ports:
        p = {"kind": k, "address": a}
        if output is not None:
            p["output"] = db.signal_by_id(output).path
        for key, val in (("data", data), ("enable", en), ("write_enable", wen), ("mask", mask)):
            if val:
                p[key] = val
        if cd:
            p["clock"] = (db.clock_domain(cd) or {}).get("clock")
        chain = db.cond_chain(cond)
        if chain:
            p["condition"] = " && ".join(cond_text(c) for c in chain)
        p["loc"] = loc(f, line)
        out.append(p)
    m = {"width": width, "depth": depth, "technology": tech, "ports": out}
    if init_sha:
        m["init"] = {"words": init_words, "sha256": init_sha}
    return m


# ---------------------------------------------------------------------------------------------- graph
class Graph:
    """Signal-level dependency graph with compiler temporaries made transparent: an edge a -> _zz_1 -> b
    reads as a -> b with the strongest kind on the way. A neighbour can be reached in several ways, so
    each maps to the set of its kinds (`x := x - y` under `when(y < x)` reads x as data and cond)."""

    def __init__(self, db: DesignDB, include_clock: bool = False):
        db.require_inout_edges()
        if db.schema not in STATE_SCHEMAS and db.q("SELECT 1 FROM mem_ports WHERE kind IN ('read_sync', 'read_write') LIMIT 1"):
            raise QueryError("synchronous memory dependency queries need rvw.designdb/17. Rebuild the database with the current SpinalDB.")
        self.db = db
        self.include_clock = include_clock
        self._hdl_aliases = ({r[0] for r in db.q(
            "SELECT target_id FROM assignments WHERE source='Yosys net alias'")}
            if db.meta.get('frontend', '').startswith('yosys-') else set())
        self._memo: dict[tuple[int, str], dict[int, frozenset]] = {}

    def aggregate(self, s: Signal) -> bool:
        # HDL vectors are endpoint views of bit nodes. Traversing through the view
        # would connect unrelated lanes merely because they share a packed net.
        return (self.db.meta.get("frontend", "").startswith("yosys-")
                and s.width > 1 and s.kind not in {"mem", "mem_read"})

    def hidden(self, s: Signal) -> bool:
        return s.generated and s.kind not in STATE_KINDS and s.direction is None and not self.aggregate(s)

    def raw(self, sid: int, direction: str) -> list[tuple[int, str]]:
        if direction == "in":
            rows = self.db.q("SELECT src, kind FROM edges WHERE dst = ?", (sid,))
        else:
            rows = self.db.q("SELECT dst, kind FROM edges WHERE src = ?", (sid,))
        return [(n, k) for n, k in rows if self.include_clock or k not in CLOCK_RELATIONS]

    def neighbours(self, sid: int, direction: str) -> dict[int, frozenset]:
        key = (sid, direction)
        if key in self._memo:
            return self._memo[key]
        out: dict[int, set] = {}
        seen = {(sid, None)}
        stack = [(n, k) for n, k in self.raw(sid, direction)]
        while stack:
            n, k = stack.pop()
            s = self.db.signal_by_id(n)
            if self.hidden(s):
                # Cells connect directly to bit vertices. A hidden net alias
                # adds no logic and must not become a feedback path through
                # its two-way view links. It is still usable as a start node.
                if n in self._hdl_aliases:
                    continue
                if (n, k) in seen:
                    continue
                seen.add((n, k))
                stack.extend((m, _strongest(k, kk)) for m, kk in self.raw(n, direction))
            else:
                out.setdefault(n, set()).add(k)
        res = {n: frozenset(ks) for n, ks in out.items()}
        self._memo[key] = res
        return res


def kinds_json(ks) -> list[str]:
    return sorted(ks, key=lambda k: KIND_RANK.get(k, 0))


def _neighbours(db: DesignDB, sid: int, direction: str, limit: int = 200) -> list[dict]:
    g = Graph(db)
    out = []
    for n, ks in sorted(g.neighbours(sid, direction).items(), key=lambda x: db.signal_by_id(x[0]).path):
        s = db.signal_by_id(n)
        out.append({"path": s.path, "kinds": kinds_json(ks), "signal_kind": s.kind})
        if len(out) >= limit:
            break
    return out


def loads(db: DesignDB, name: str, limit: int = 500) -> dict:
    s = db.resolve_one(name)
    g = Graph(db)
    readers = g.neighbours(s.id, "out")
    stmts = db.q("SELECT r.assignment_id, r.kind FROM assign_reads r WHERE r.signal_id = ? LIMIT ?", (s.id, limit))
    by_assign = {}
    for aid, k in stmts:
        by_assign.setdefault(aid, set()).add(k)
    uses = []
    if by_assign:
        ids = list(by_assign)
        for a in _assignment_rows(db, f"a.id IN ({','.join('?' * len(ids))})", ids):
            a["read_as"] = sorted(by_assign[a["id"]])
            uses.append(a)
    conds = db.q("SELECT c.id, c.kind, c.expr, c.keys, f.path, c.line, c.component_id FROM cond_reads r JOIN conds c ON c.id = r.cond_id "
                 "LEFT JOIN files f ON f.id = c.file_id WHERE r.signal_id = ? LIMIT ?", (s.id, limit))
    cond_uses = []
    for cid, k, expr, keys, f, line, comp in conds:
        n = db.q("WITH RECURSIVE sub(id) AS (SELECT ? UNION ALL SELECT c.id FROM conds c JOIN sub ON c.parent_id = sub.id) "
                 "SELECT count(*) FROM assignments WHERE cond_id IN (SELECT id FROM sub)", (cid,))[0][0]
        cond_uses.append({"condition": cond_text({"kind": k, "expr": expr, "keys": keys}), "loc": loc(f, line),
                          "in_component": db.component(comp)["path"] or db.top, "guarded_assignments": n})
    out = sorted(({"path": db.signal_by_id(n).path, "kinds": kinds_json(ks), "signal_kind": db.signal_by_id(n).kind}
                  for n, ks in readers.items()), key=lambda x: x["path"])
    return {"signal": db.signal_json(s), "readers": out[:limit], "reader_count": len(out),
            "statements": uses, "conditions": cond_uses}


def _bfs(db: DesignDB, starts: list[Signal], direction: str, depth: int, *, stop_at_regs: bool, kinds: set[str] | None,
         limit: int, include_clock: bool) -> dict:
    g = Graph(db, include_clock=include_clock)
    start_ids = {s.id for s in starts}
    dist = {s.id: 0 for s in starts}
    edges = []
    q = deque(s.id for s in starts)
    truncated = False
    while q:
        u = q.popleft()
        if dist[u] >= depth:
            continue
        su = db.signal_by_id(u)
        if u not in start_ids and g.aggregate(su):
            continue
        if stop_at_regs and dist[u] > 0 and su.kind in STATE_KINDS:
            continue
        for v, ks in sorted(g.neighbours(u, direction).items()):
            if kinds:
                ks = ks & kinds
                if not ks:
                    continue
            edges.append((u, v, ks) if direction == "out" else (v, u, ks))
            if v not in dist:
                if len(dist) >= limit:
                    truncated = True
                    continue
                dist[v] = dist[u] + 1
                q.append(v)
    nodes = []
    for sid, dd in sorted(dist.items(), key=lambda x: (x[1], db.signal_by_id(x[0]).path)):
        if sid in start_ids:
            continue
        s = db.signal_by_id(sid)
        n = db.signal_json(s, brief=True)
        n["depth"] = dd
        nodes.append(n)
    p = lambda i: db.signal_by_id(i).path  # noqa: E731
    return {"start": [s.path for s in starts], "direction": "fanin" if direction == "in" else "fanout",
            "depth": depth, "nodes": nodes, "edges": [{"src": p(a), "dst": p(b), "kinds": kinds_json(k)} for a, b, k in edges],
            "truncated": truncated,
            "registers": sorted({n["path"] for n in nodes if n["kind"] == "reg"}),
            "ports": sorted({n["path"] for n in nodes if n.get("direction")})}


def fanin(db: DesignDB, name: str, depth: int = 1, stop_at_regs: bool = False, kinds: list[str] | None = None,
          limit: int = 500, include_clock: bool = False) -> dict:
    return _bfs(db, db.resolve(name, allow_group=True), "in", depth, stop_at_regs=stop_at_regs,
                kinds=set(kinds) if kinds else None, limit=limit, include_clock=include_clock)


def fanout(db: DesignDB, name: str, depth: int = 1, stop_at_regs: bool = False, kinds: list[str] | None = None,
           limit: int = 500, include_clock: bool = False) -> dict:
    return _bfs(db, db.resolve(name, allow_group=True), "out", depth, stop_at_regs=stop_at_regs,
                kinds=set(kinds) if kinds else None, limit=limit, include_clock=include_clock)


def path(db: DesignDB, a: str, b: str, *, comb_only: bool = False, data_only: bool = False, max_paths: int = 3,
         max_nodes: int = 2_000_000) -> dict:
    """Shortest dependency paths from A (what is read) to B (what is driven), through logic and registers."""
    srcs = db.resolve(a, allow_group=True)
    dsts = db.resolve(b, allow_group=True)
    dst_ids = {s.id for s in dsts}
    g = Graph(db)
    parents: dict[int, list[tuple[int, str]]] = {s.id: [] for s in srcs}
    dist = {s.id: 0 for s in srcs}
    q = deque(s.id for s in srcs)
    found_at = None
    # Arrivals at a destination are kept apart from `parents`, so a destination that is also a
    # source (`path rob_head rob_head`: a feedback loop, or `x := x - y`) is found after >= 1 hop.
    arrive: dict[int, list[tuple[int, str]]] = {}
    while q:
        u = q.popleft()
        if found_at is not None and dist[u] >= found_at:
            break
        su = db.signal_by_id(u)
        if dist[u] > 0 and g.aggregate(su):
            continue
        if comb_only and dist[u] > 0 and su.kind in STATE_KINDS:
            continue
        for v, ks in g.neighbours(u, "out").items():
            if data_only:
                ks = ks - CONTROL
                if not ks:
                    continue
            k = max(ks, key=lambda x: -KIND_RANK.get(x, 0))  # weakest kind = most direct link
            if v in dst_ids and (found_at is None or dist[u] + 1 == found_at):
                found_at = dist[u] + 1
                arrive.setdefault(v, []).append((u, k))
            if v not in dist:
                dist[v] = dist[u] + 1
                parents[v] = [(u, k)]
                q.append(v)
            elif dist[v] == dist[u] + 1:
                parents[v].append((u, k))
        if len(dist) > max_nodes:
            break
    if not arrive:
        return {"from": [s.path for s in srcs][:20], "to": [s.path for s in dsts][:20], "found": False,
                "searched_signals": len(dist),
                "hint": "no dependency path; try the other direction, drop --comb-only/--data-only, or check `fanin`"}
    paths = []

    for h, via in arrive.items():
        for u, k in via:
            # Each frame holds the next parent to visit. Keep one suffix instead of copying it
            # at every hop, so a long path uses linear memory and no Python recursion.
            suffix = [(h, k)]
            stack = [(u, iter(parents[u]))]
            while stack and len(paths) < max_paths:
                v, choices = stack[-1]
                if not parents[v]:
                    paths.append(list(reversed(suffix + [(v, None)])))
                    stack.pop()
                    if stack:
                        suffix.pop()
                    continue
                parent = next(choices, None)
                if parent is None:
                    stack.pop()
                    if stack:
                        suffix.pop()
                else:
                    prev, kind = parent
                    suffix.append((v, kind))
                    stack.append((prev, iter(parents[prev])))
            if len(paths) >= max_paths:
                break
        if len(paths) >= max_paths:
            break
    out = []
    for p in paths:
        hops = []
        for i, (sid, _) in enumerate(p):
            s = db.signal_by_id(sid)
            hop = db.signal_json(s, brief=True)
            if i > 0:
                prev, kind = p[i - 1][0], p[i][1]
                hop["via"] = kind
                hop["logic"] = _link(db, prev, sid)
            hops.append(hop)
        out.append({"length": len(p) - 1, "register_stages": sum(1 for h in hops[1:] if h["kind"] in STATE_KINDS),
                    "hops": hops})
    return {"from": [s.path for s in srcs][:20], "to": [s.path for s in dsts][:20], "found": True, "paths": out}


def _link(db: DesignDB, src: int, dst: int) -> list[dict]:
    """The statements of `dst` that read `src` (directly or through compiler temporaries)."""
    rows = db.q("SELECT DISTINCT a.id FROM assignments a JOIN assign_reads r ON r.assignment_id = a.id "
                "WHERE a.target_id = ? AND r.signal_id = ? LIMIT 5", (dst, src))
    if rows:
        return [{k: a[k] for k in ("source", "condition", "range", "loc") if a.get(k)}
                for a in _assignment_rows(db, f"a.id IN ({','.join(str(r[0]) for r in rows)})", ())]
    rows = db.q("SELECT DISTINCT c.id FROM cond_reads r JOIN conds c ON c.id = r.cond_id WHERE r.signal_id = ? LIMIT 50", (src,))
    for (cid,) in rows:
        hit = db.q("WITH RECURSIVE sub(id) AS (SELECT ? UNION ALL SELECT c.id FROM conds c JOIN sub ON c.parent_id = sub.id) "
                   "SELECT a.id FROM assignments a WHERE a.target_id = ? AND a.cond_id IN (SELECT id FROM sub) LIMIT 3", (cid, dst))
        if hit:
            return [{k: a[k] for k in ("source", "condition", "range", "loc") if a.get(k)}
                    for a in _assignment_rows(db, f"a.id IN ({','.join(str(h[0]) for h in hit)})", ())]
    # through a temporary: show the target's assignments
    return [{k: a[k] for k in ("source", "condition", "range", "loc") if a.get(k)}
            for a in _assignment_rows(db, "a.target_id = ? AND a.kind != 'init'", (dst,))[:3]]


# ---------------------------------------------------------------------------------------------- search
def search(db: DesignDB, pattern: str, *, kind: str | None = None, regex: bool = False, scope: str | None = None,
           include_generated: bool = False, limit: int = 100) -> dict:
    where, args = ["s.pruned = 0"], []
    if not include_generated:
        where.append("s.generated = 0")
    if kind == "port":
        where.append("s.direction IS NOT NULL")
    elif kind in ("reg", "wire", "mem"):
        where.append("s.kind = ?")
        args.append(kind)
    scope_path = ""
    if scope:
        c = db.resolve_component(scope)
        scope_path = c["path"]
        if c["path"]:
            where.append("(s.path LIKE ? ESCAPE '\\')")
            args.append(c["path"].replace("_", "\\_") + ".%")
    if regex:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise QueryError(f'invalid regular expression: {exc}') from exc
        match = lambda t: t is not None and rx.search(t) is not None  # noqa: E731
    else:
        pat = pattern if any(ch in pattern for ch in "*?[") else f"*{pattern}*"
        pat = ("" if pat.startswith("*") else "*") + pat + ("" if pat.endswith("*") else "*")  # unanchored
        match = lambda t: t is not None and fnmatch.fnmatchcase(t.lower(), pat.lower())  # noqa: E731
    out, total = [], 0
    if kind in (None, "component"):
        for cid, cpath, module, cls in db.q("SELECT id, path, module, class_name FROM components"):
            if scope_path and cpath != scope_path and not cpath.startswith(scope_path + "."):
                continue
            if match(cpath) or match(module) or match(cls):
                total += 1
                if len(out) < limit:
                    out.append({"component": cpath or db.top, "module": module, "class": cls})
    if kind != "component":
        cur = db.conn.execute(f"SELECT s.id, s.path, s.spinal_path FROM signals s WHERE {' AND '.join(where)}", args)
        for sid, p, sp in cur:
            if match(p) or match(sp):
                total += 1
                if len(out) < limit:
                    out.append(db.signal_json(db.signal_by_id(sid), brief=True))
    return {"pattern": pattern, "matches": out, "total": total, "truncated": total > len(out)}


# ---------------------------------------------------------------------------------------------- hierarchy
def hierarchy(db: DesignDB, path: str | None = None, depth: int = 2) -> dict:
    root = db.resolve_component(path)

    def node(c: dict, d: int) -> dict:
        n = {"path": c["path"] or db.top, "name": c["name"], "module": c["module"], "class": c["class"], "loc": c["loc"]}
        if c["blackbox"]:
            n["blackbox"] = True
        kids = db.q("SELECT id FROM components WHERE parent_id = ? ORDER BY name", (c["id"],))
        if d < depth:
            n["children"] = [node(db.component(k[0]), d + 1) for k in kids]
        elif kids:
            n["children_count"] = len(kids)
        return n

    return {"root": node(root, 0)}


def component(db: DesignDB, path: str | None) -> dict:
    c = db.resolve_component(path)
    cid = c["id"]
    sigs = db.signals_where("s.component_id = ? AND s.pruned = 0", (cid,))
    ports = [s for s in sigs if s.direction]
    out = {"component": c["path"] or db.top, "name": c["name"], "module": c["module"], "class": c["class"], "loc": c["loc"]}
    if c["parent_id"]:
        out["parent"] = db.component(c["parent_id"])["path"] or db.top
    if c["blackbox"]:
        out["blackbox"] = True
    out["ports"] = [{"name": s.name, "spinal": s.spinal_path.split(".", c["depth"])[-1] if c["depth"] else s.spinal_path,
                     "direction": s.direction, "type": s.type, "width": s.width,
                     **({"data_type": s.data_type} if s.data_type else {}),
                     **({"clock_role": s.clock_role} if s.clock_role else {})} for s in ports]
    params = hdl_parameters(db)
    if params is not None and c["path"] in params:
        out["parameters"] = params[c["path"]]
    out["interfaces"] = interfaces(db, cid, c["path"], max_depth=3)
    out["children"] = [{"name": r[1], "module": r[2], "class": r[3]}
                       for r in db.q("SELECT id, name, module, class_name FROM components WHERE parent_id = ? ORDER BY name", (cid,))]
    out["registers"] = [_reg_json(db, s) for s in sigs if s.kind == "reg" and not s.generated]
    out["generated_registers"] = sum(1 for s in sigs if s.kind == "reg" and s.generated)
    out["memories"] = []
    for s in sigs:
        if s.kind == "mem":
            m = _memory(db, s) or {}
            out["memories"].append({"name": s.name, "width": m.get("width"), "depth": m.get("depth"),
                                    "ports": [p["kind"] for p in m.get("ports", [])], "loc": loc(s.file, s.line)})
    areas = db.q("SELECT a.id, a.path, a.class_name, f.path, a.line FROM areas a LEFT JOIN files f ON f.id = a.file_id "
                 "WHERE a.component_id = ? ORDER BY a.path", (cid,))
    counts = {}
    for s in sigs:
        if s.area_id:
            n = counts.setdefault(s.area_id, [0, 0])
            n[0] += 1
            n[1] += s.kind == "reg"
    out["areas"] = [{"area": p, "class": cls, "signals": counts.get(aid, [0, 0])[0], "registers": counts.get(aid, [0, 0])[1],
                     "loc": loc(f, line)} for aid, p, cls, f, line in areas]
    out["counts"] = {"signals": len(sigs), "named_signals": sum(1 for s in sigs if not s.generated), "ports": len(ports),
                     "registers": sum(1 for s in sigs if s.kind == "reg"), "memories": len(out["memories"]),
                     "children": len(out["children"])}
    return out


def hdl_parameters(db: DesignDB) -> dict | None:
    """Per-instance parameter values recorded by an HDL front end ({component path: {name: value}})."""
    rows = db.q("SELECT encoding, content FROM artifacts WHERE name = 'hdl/parameters.json'")
    if not rows:
        return None
    enc, content = rows[0]
    return json.loads(gzip.decompress(content) if enc == "gzip" else content)


def _reg_json(db: DesignDB, s: Signal) -> dict:
    cd = db.clock_domain(s.clock_domain_id) or {}
    d = {"path": s.path, "spinal_path": s.spinal_path, "type": s.type, "width": s.width, "clock": cd.get("clock"),
         "reset_value": s.reset_value, "loc": loc(s.file, s.line)}
    if cd.get("clock_enable"):
        d["clock_enable"] = cd["clock_enable"]
    return d


def regs(db: DesignDB, path: str | None, recursive: bool = False, include_generated: bool = False, limit: int = 2000) -> dict:
    c = db.resolve_component(path)
    if recursive:
        prefix = c["path"]
        where = "s.kind = 'reg' AND s.pruned = 0" + ("" if not prefix else " AND (s.path LIKE ? ESCAPE '\\')")
        args = () if not prefix else (prefix.replace("_", "\\_") + ".%",)
    else:
        where, args = "s.kind = 'reg' AND s.pruned = 0 AND s.component_id = ?", (c["id"],)
    if not include_generated:
        where += " AND s.generated = 0"
    sigs = db.signals_where(where, args)
    sigs.sort(key=lambda s: s.path)
    return {"component": c["path"] or db.top, "recursive": recursive, "count": len(sigs),
            "registers": [_reg_json(db, s) for s in sigs[:limit]], "bits": sum(s.width or 0 for s in sigs)}


# ---------------------------------------------------------------------------------------------- info / export
def info(db: DesignDB) -> dict:
    counts = {t: db.q(f"SELECT count(*) FROM {t}")[0][0]
              for t in ("components", "signals", "memories", "assignments", "conds", "edges", "pdg_vertices", "pdg_edges")}
    counts["registers"] = db.q("SELECT count(*) FROM signals WHERE kind = 'reg' AND pruned = 0")[0][0]
    counts["named_signals"] = db.q("SELECT count(*) FROM signals WHERE generated = 0 AND pruned = 0")[0][0]
    return {"db": str(db.path), "size_bytes": db.input.size, "meta": db.meta, "counts": counts,
            "clock_domains": [db.clock_domain(r[0]) for r in db.q("SELECT id FROM clock_domains")],
            "artifacts": [{"name": n, "media_type": m, "size": s} for n, m, s in db.q("SELECT name, media_type, size FROM artifacts")],
            "rtl_files": [r[0] for r in db.q("SELECT path FROM rtl_files")],
            "warnings": [f"{s}: {m}" for s, m in db.q("SELECT source, message FROM warnings LIMIT 50")]}


ARTIFACT_ALIASES = {"blocks": "blocks.json", "pdg": "pdg.json", "hgldd": "hgldd/"}


def export(db: DesignDB, artifact: str, out: str) -> dict:
    """Writes an artifact stored in the database (`blocks`, `pdg`, `hgldd`) to a file. Names ending in
    `.gz` stay gzipped."""
    name = ARTIFACT_ALIASES.get(artifact, artifact)
    rows = db.q("SELECT name, encoding, content FROM artifacts WHERE name = ? OR (? LIKE '%/' AND name LIKE ? || '%')",
                (name, name, name))
    if not rows:
        have = [r[0] for r in db.q("SELECT name FROM artifacts")]
        raise QueryError(f"no artifact {artifact!r} in {db.path}", have)
    n, enc, content = rows[0]
    data = content if out.endswith(".gz") or enc != "gzip" else gzip.decompress(content)
    destination = Path(out).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".rvw-export-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"artifact": n, "out": str(Path(out).resolve()), "bytes": len(data)}
