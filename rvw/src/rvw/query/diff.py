"""Compare stable hardware paths and typed keys. See SpinalDB/README.md for the key contract.

Generated internals are compared by content. Ports retain their external paths.
Incomplete keys cannot establish equality. Display text alone masks generated names.
Composite comparison values use structured lists and dictionaries, with tag order retained.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from .db import SCHEMA, DesignDB, QueryError
from .ops import KIND_RANK, cond_text

_ZZ = re.compile(r"\b_zz_\w+")
# The line suffix of a name Spinal (or SpinalTrace's naming phase) derives from a source line.
_LINE_NAME = re.compile(r"^(\w+?)_l\d+(?:_\d+)?$")
# A signal reference in display text: an RTL path relative to the statement's component.
_TOKEN = re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")


# A typed key that cannot prove equality (SpinalDB: expansion bound reached, combinational loop cut).
_INCOMPLETE = re.compile(r"\$incomplete:|\bh!:")


def _enc(value) -> str:
    """The canonical text of a structured comparison value (JSON with sorted keys): one string per
    value, never the same for two different values; used to sort, deduplicate and hash them."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _incomplete(value) -> bool:
    """True when a key, or any key inside a structured value (dict, list), is incomplete."""
    if isinstance(value, str):
        return bool(_INCOMPLETE.search(value))
    if isinstance(value, dict):
        return any(_incomplete(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_incomplete(v) for v in value)
    return False


def _masker(line_names: set[str]):
    """Display-text normalizer: `_zz_` numbers, and the line suffix of the names in `line_names` (the
    signals this database marks generated whose name ends in `_l<N>`). Any other name is kept."""
    def leaf(m: re.Match) -> str:
        tok = m.group(0)
        head, _, last = tok.rpartition(".")
        if last in line_names:
            return (head + "." if head else "") + _LINE_NAME.sub(r"\1_l*", last)
        return tok

    def norm(t: str | None) -> str | None:
        if t is None:
            return None
        return _ZZ.sub("_zz_*", _TOKEN.sub(leaf, t) if line_names else t)
    return norm


def _enum(v):
    """A Spinal enum value as SpinalDB wrote it: `FALLING`, or `toplevel/FALLING` when the value was
    named inside a component."""
    return None if v is None else str(v).rsplit("/", 1)[-1]


def _active(high) -> str:
    return "active-high" if str(high).lower() in ("true", "1") else "active-low" if high is not None else "active-?"


def _domain(row) -> dict:
    """A clock domain with every control a register or memory port depends on: clock and edge, reset
    signal, kind and polarity, clock enable and its polarity, soft reset and its polarity. A dict of
    its parts, so no signal name can pose as another part (as in a joined string)."""
    clock, reset, kind, high, enable, soft, edge, enable_high, soft_high = row
    out = {"clock": clock, "edge": _enum(edge) or "?"}
    if reset:
        out.update(reset=reset, reset_kind=_enum(kind) or "?", reset_polarity=_active(high))
    elif kind:
        out["reset_kind"] = _enum(kind)
    if enable:
        out.update(enable=enable, enable_polarity=_active(enable_high))
    if soft:
        out.update(soft_reset=soft, soft_reset_polarity=_active(soft_high))
    return out


def _in_scope(path: str, scope: str | None) -> bool:
    return not scope or path == scope or path.startswith(scope + ".")


class _Snapshot:
    def __init__(self, db: DesignDB, scope: str | None):
        self.db = db
        self.scope = scope
        rows = db.q("SELECT s.id, s.path, s.kind, s.direction, s.type, s.width, s.data_type, s.clock_domain_id, s.reset_value, "
                    "s.generated, s.pruned, s.clock_role, s.spinal_path, s.tags, s.component_id, s.name, s.port_index "
                    "FROM signals s")
        _norm = self.norm = _masker({r[15] for r in rows if r[9] and _LINE_NAME.match(r[15] or "")})
        cd_rows = db.q("SELECT id, clock, reset, reset_kind, reset_active_high, clock_enable, soft_reset, clock_edge, "
                       "clock_enable_active_high, soft_reset_active_high, clock_key, reset_key, clock_enable_key, "
                       "soft_reset_key FROM clock_domains")
        cds = {r[0]: r[1] for r in cd_rows}
        # The domain's controls, and the typed keys of its control signals as [role, key] pairs.
        # Every value diff compares that has several parts is a dict or list of them, never a joined
        # string: two different part lists cannot compare equal (keys may hold any separator).
        self.domains = {r[0]: _domain(r[1:10]) for r in cd_rows}
        self.domain_keys = {r[0]: [[n, k] for n, k in zip(("clock", "reset", "enable", "soft_reset"), r[10:])
                                   if k is not None] for r in cd_rows}
        incomplete_domains = {cid for cid, k in self.domain_keys.items() if _incomplete(k)}
        # Generated registers (`RegNext(x) init k`) have unstable `_zz_` names and are left out of
        # `signals`; their state is compared through the named signals that read them.
        self.gen_regs = {}
        self.incomplete_signals: set[str] = set()
        self.by_id = {}
        self.signals = {}
        ports_of: dict[int, list[tuple[int, str]]] = defaultdict(list)
        for sid, path, kind, d, typ, w, dt, cd, rv, gen, pruned, role, sp, tags, comp, name, pidx in rows:
            if pidx is not None:
                ports_of[comp].append((pidx, [name, d, typ, w]))
            self.by_id[sid] = (path, bool(gen) and kind not in ("reg", "mem") and d is None, bool(pruned))
            # Incomplete declarations cannot prove equality, even for an unread temporary or a
            # pruned signal. Keep their markers before filtering generated internal declarations.
            if _in_scope(path, scope) and (_incomplete(tags) or _incomplete(typ) or cd in incomplete_domains):
                self.incomplete_signals.add(path)
            if gen and kind == "reg" and not pruned:
                self.gen_regs[sid] = {"register": typ or dt, "width": w, "clock": self.domains.get(cd),
                                      "clock_logic": self.domain_keys.get(cd), "reset_value": _norm(rv)}
                if tags:
                    self.gen_regs[sid]["tags"] = tags
            if (gen and d is None) or pruned or not _in_scope(path, scope):
                continue
            self.signals[path] = {"kind": kind, "direction": d, "type": typ, "width": w, "data_type": dt,
                                  "clock": cds.get(cd), "clock_domain": self.domains.get(cd), "reset_value": _norm(rv),
                                  "clock_role": role, "spinal_path": sp, "tags": tags}
            if cd is not None:
                self.signals[path]["clock_domain_logic"] = self.domain_keys.get(cd)
        self.cond_keys = dict(db.q("SELECT id, key FROM conds"))
        # Components: definition, class, BlackBox generics and body fingerprint, and their other
        # statements (assertions; a statement SpinalDB does not model is an incomplete key).
        blackboxes = dict(db.q("SELECT component_id, key FROM blackboxes"))
        statements = defaultdict(list)
        for cid, kind, key, cd, cond in db.q("SELECT component_id, kind, key, clock_domain_id, cond_id FROM statements ORDER BY id"):
            st = {"kind": kind, "key": key}
            if cd is not None:
                st.update(clock=self.domains.get(cd), clock_logic=self.domain_keys.get(cd))
            if cond is not None:
                st["when"] = self._cond_key_chain(cond)
            statements[cid].append(st)
        self.components = {}
        self.incomplete_components: set[str] = set()
        for cid, path, module, cls, tags in db.q("SELECT id, path, module, class_name, tags FROM components"):
            if _in_scope(path, scope):
                name = path or "<top>"
                self.components[name] = {"module": module, "class": cls}
                if ports_of.get(cid):  # the module's ports in declaration order
                    self.components[name]["ports"] = [p for _, p in sorted(ports_of[cid], key=lambda x: x[0])]
                if tags:  # instance and definition attributes, emitted into the Verilog
                    self.components[name]["tags"] = tags
                if cid in blackboxes:
                    self.components[name]["blackbox"] = blackboxes[cid]
                if statements.get(cid):
                    self.components[name]["statements"] = statements[cid]
                if _incomplete(blackboxes.get(cid)) or _incomplete(tags) or \
                        any(_incomplete(t) for t in statements.get(cid, ())):
                    self.incomplete_components.add(name)
        ports = defaultdict(list)
        incomplete_mems: set[int] = set()
        for mid, key, cd, cond in db.q("SELECT memory_id, key, clock_domain_id, cond_id FROM mem_ports"):
            # The typed key of the port: every port setting (read-under-write, during-write, width,
            # vital) and the typed keys of its address, data, enables and mask.
            port = {"key": key}
            if cd is not None:
                port.update(clock=self.domains.get(cd), clock_logic=self.domain_keys.get(cd))
            if cond is not None:
                port["when"] = self._cond_key_chain(cond)
            ports[mid].append(port)
            if _incomplete(port):
                incomplete_mems.add(mid)
        self.memories = {}
        for mid, p, w, d, h, n, key in db.q("SELECT id, path, width, depth, init_sha256, init_words, key FROM memories"):
            if _in_scope(p, scope):
                self.memories[p] = {"width": w, "depth": d, "init_sha256": h, "init_words": n, "key": key,
                                    "ports": sorted(ports[mid], key=_enc)}
                if _incomplete(key):
                    incomplete_mems.add(mid)
        # Paths whose comparison rests on an incomplete typed key (see `_INCOMPLETE`).
        self.incomplete: set[str] = {p for mid, p in db.q("SELECT id, path FROM memories")
                                     if mid in incomplete_mems and _in_scope(p, scope)} | self.incomplete_signals \
            | self.incomplete_components

    def connections(self) -> set[tuple[str, str, str]]:
        """Named-signal dependency edges, temporaries collapsed."""
        self.db.require_inout_edges()
        out_edges = defaultdict(list)
        for src, dst, kind in self.db.q("SELECT src, dst, kind FROM edges"):
            out_edges[src].append((dst, kind))
        memo: dict[int, dict[int, str]] = {}

        def reach(g: int, stack: set) -> dict[int, str]:
            if g in memo:
                return memo[g]
            res: dict[int, str] = {}
            stack.add(g)
            for d, k in out_edges.get(g, ()):
                path, hidden, pruned = self.by_id[d]
                if pruned:
                    continue
                if hidden:
                    if d in stack:
                        continue
                    for dd, kk in reach(d, stack).items():
                        k2 = k if KIND_RANK.get(k, 0) >= KIND_RANK.get(kk, 0) else kk
                        res[dd] = k2 if dd not in res or KIND_RANK.get(k2, 0) > KIND_RANK.get(res[dd], 0) else res[dd]
                else:
                    res[d] = k if d not in res or KIND_RANK.get(k, 0) > KIND_RANK.get(res[d], 0) else res[d]
            stack.discard(g)
            memo[g] = res
            return res

        conns = set()
        for src, (path, hidden, pruned) in self.by_id.items():
            if hidden or pruned or src not in out_edges:
                continue
            for dst, k in reach(src, set()).items():
                dpath = self.by_id[dst][0]
                if _in_scope(dpath, self.scope) or _in_scope(path, self.scope):
                    conns.add((path, dpath, k))
        return conns

    def _cond_key_chain(self, cid: int | None) -> list[list[str]]:
        """The enclosing conditions, outermost first, as [kind, typed key] pairs."""
        keys = []
        while cid is not None:
            r = self.db.conn.execute("SELECT parent_id, kind FROM conds WHERE id = ?", (cid,)).fetchone()
            if r is None:
                break
            keys.append([r[1], self.cond_keys.get(cid)])
            cid = r[0]
        return list(reversed(keys))

    def assignments(self) -> dict[str, list[tuple[str, str]]]:
        """Per named signal: (display text, typed key) of each assignment in order, `init` (reset
        value) included. The key (assignment, enclosing conditions, and the state of every generated
        register it reads) is what is compared; the text is what is shown."""
        out = defaultdict(list)
        rows = self.db.q("SELECT a.id, a.target_id, a.kind, a.range, a.source, a.enable, a.mask, a.cond_id, a.key "
                         "FROM assignments a ORDER BY a.seq")
        reads: dict[int, list[int]] = defaultdict(list)
        for aid, sid in self.db.q("SELECT assignment_id, signal_id FROM assign_reads"):
            reads[aid].append(sid)
        cond_reads: dict[int, list[int]] = defaultdict(list)
        for cid, sid in self.db.q("SELECT cond_id, signal_id FROM cond_reads"):
            cond_reads[cid].append(sid)
        parent = dict(self.db.q("SELECT id, parent_id FROM conds"))
        by_target: dict[int, list[int]] = defaultdict(list)  # assignment ids of each signal, in order
        conds: dict[int, int | None] = {}
        gen_logic: dict[int, list[dict]] = defaultdict(list)
        self.temp_logic: dict[int, list[str]] = defaultdict(list)
        named: list[tuple[int, str, str, dict]] = []
        for aid, tid, kind, rng, src, en, mask, cond, key in rows:
            path, hidden, pruned = self.by_id[tid]
            typed = {"kind": kind, "key": key, "when": self._cond_key_chain(cond)}
            # A generated or pruned target can hide an incomplete assignment or condition too.
            if _in_scope(path, self.scope) and _incomplete(typed):
                self.incomplete.add(path)
            if pruned:
                continue
            by_target[tid].append(aid)
            conds[aid] = cond
            if tid in self.gen_regs:
                gen_logic[tid].append(typed)
            if kind == "init" and hidden or (not hidden and not _in_scope(path, self.scope)):
                continue
            chain = self.db.cond_chain(cond)
            text = (("init" if kind == "init" else "") + f"{rng or ''} := {src}" + (f" [enable {en}]" if en else "") +
                    (f" [mask {mask}]" if mask else "") +
                    (f" when {' && '.join(cond_text(c) for c in chain)}" if chain else ""))
            if hidden:
                self.temp_logic[tid].append(self.norm(f"{path} {text}"))
                continue
            named.append((aid, path, self.norm(text), typed))

        def read_by(aid: int) -> list[int]:
            """Signals an assignment reads, in its source and in its enclosing conditions."""
            out_ids, cid = list(reads.get(aid, ())), conds.get(aid)
            while cid is not None:
                out_ids += cond_reads.get(cid, ())
                cid = parent.get(cid)
            return out_ids

        def gens_read(aids: list[int]) -> list[int]:
            """Generated registers the assignments read, directly or through compiler temporaries."""
            found, seen, todo = [], set(), [s for a in aids for s in read_by(a)]
            while todo:
                sid = todo.pop()
                if sid in seen or sid not in self.by_id:
                    continue
                seen.add(sid)
                if sid in self.gen_regs:
                    found.append(sid)
                elif self.by_id[sid][1]:
                    todo += [s for a in by_target.get(sid, ()) for s in read_by(a)]
            return found

        memo: dict[int, dict] = {}

        def distinct(values) -> list:
            """Values without repeats, in the order of their canonical text."""
            by_text = {_enc(v): v for v in values}
            return [by_text[t] for t in sorted(by_text)]

        def describe(gid: int, stack: set) -> dict:
            """A generated register by content: type, clock domain, reset value, its typed assignments
            (init included) and the generated registers it reads. Names are not part of it. A long
            description becomes the hash of its canonical text (`h!:` when it holds an incomplete key)."""
            if gid in memo:
                return memo[gid]
            if gid in stack:
                return {"loop": True}
            stack.add(gid)
            inner = distinct(describe(g, stack) for g in gens_read(by_target.get(gid, [])))
            stack.discard(gid)
            value = {"register": self.gen_regs[gid], "assignments": gen_logic[gid]}
            if inner:
                value["reads"] = inner
            text = _enc(value)
            if len(text) > 600:
                value = {"hash": ("h!:" if _incomplete(value) else "h:") + hashlib.sha256(text.encode()).hexdigest()[:16]}
            memo[gid] = value
            return value

        self.generated: dict[str, list[str]] = defaultdict(list)
        named_ids: dict[int, str] = {}
        for aid, path, text, typed in named:
            gens = distinct(describe(g, set()) for g in gens_read([aid]))
            for g in gens:
                if g not in self.generated[path]:
                    self.generated[path].append(g)
            named_ids[aid] = path
            if gens:
                typed = {**typed, "reads_generated": gens}
            if _incomplete(typed):
                self.incomplete.add(path)
            out[path].append((text, typed))
        # Temporaries each named signal reads directly: their logic is shown when only the key changed.
        self.reads_temps: dict[str, list[int]] = defaultdict(list)
        for aid, sid in self.db.q("SELECT assignment_id, signal_id FROM assign_reads"):
            path = named_ids.get(aid)
            if path is not None and sid in self.temp_logic and sid not in self.reads_temps[path]:
                self.reads_temps[path].append(sid)
        return out

    def temporaries_of(self, path: str) -> list[str]:
        return [t for sid in self.reads_temps.get(path, ()) for t in self.temp_logic[sid]][:20]


def _dict_diff(old: dict, new: dict, limit: int) -> dict:
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for k in sorted(set(old) & set(new)):
        if old[k] != new[k]:
            fields = {f: {"old": old[k].get(f), "new": new[k].get(f)} for f in set(old[k]) | set(new[k])
                      if old[k].get(f) != new[k].get(f)}
            changed.append({"path": k, "changes": fields})
    return {"added": [{"path": a, **new[a]} for a in added[:limit]], "removed": [{"path": r, **old[r]} for r in removed[:limit]],
            "changed": changed[:limit], "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)}}


def diff(old: DesignDB, new: DesignDB, *, scope: str | None = None, limit: int = 200, connections: bool = True) -> dict:
    for d in (old, new):
        if d.schema != SCHEMA:
            # Older keys cannot establish equality under the current contract.
            raise QueryError(f"{d.path} has schema {d.schema}; diff needs {SCHEMA} (typed keys under the allow-list "
                             f"rule). Rebuild the database with the current SpinalDB.")
    capture_incomplete = []
    for side, database in (("old", old), ("new", new)):
        try:
            record = json.loads(database.meta.get("input_capture", "null"))
            valid = (isinstance(record, dict) and record.get("schema") == "rvw.capture/1" and
                     all(isinstance(record.get(k), list) for k in ("files", "trees", "tools", "git_refs", "problems")) and
                     isinstance(record.get("env"), dict) and not record["problems"])
        except (ValueError, TypeError):
            valid = False
        if not valid:
            capture_incomplete.append(side)
    scope = old.normalize(scope) if scope else None
    if scope and not any(_in_scope(path, scope) for db in (old, new)
                         for (path,) in db.q("SELECT path FROM components UNION SELECT path FROM signals")):
        raise QueryError(f"no diff scope {scope!r} in either database")
    a, b = _Snapshot(old, scope), _Snapshot(new, scope)
    if scope and not (a.components or b.components or a.signals or b.signals or a.memories or b.memories):
        raise QueryError(f"no comparable objects in diff scope {scope!r}; choose a named signal or component")
    out = {"old": {"db": str(old.path), "toplevel": old.top, **{k: old.meta.get(k) for k in ("config", "core_rev", "created")
                                                                 if old.meta.get(k)}},
           "new": {"db": str(new.path), "toplevel": new.top, **{k: new.meta.get(k) for k in ("config", "core_rev", "created")
                                                                 if new.meta.get(k)}}}
    if scope:
        out["scope"] = scope
    # Emission policies apply to the whole design, including scoped comparisons.
    config_old, config_new = old.meta.get("emission_config"), new.meta.get("emission_config")
    config_changed = config_old != config_new
    config_incomplete = not config_old or not config_new or _incomplete([config_old, config_new])
    out["emission_config"] = {"old": config_old, "new": config_new, "changed": config_changed}
    out["components"] = _dict_diff(a.components, b.components, limit)
    sigs = _dict_diff(a.signals, b.signals, limit)
    ports_old = {k: v for k, v in a.signals.items() if v["direction"]}
    ports_new = {k: v for k, v in b.signals.items() if v["direction"]}
    regs_old = {k: v for k, v in a.signals.items() if v["kind"] == "reg"}
    regs_new = {k: v for k, v in b.signals.items() if v["kind"] == "reg"}
    out["ports"] = _dict_diff(ports_old, ports_new, limit)
    # Components whose module declares the same ports in another order (also a `ports` change of the
    # component): a positional instantiation or an external tool reading the module sees other hardware.
    out["ports"]["reordered"] = sorted(
        k for k in set(a.components) & set(b.components)
        if a.components[k].get("ports") != b.components[k].get("ports")
        and sorted(a.components[k].get("ports") or (), key=_enc) == sorted(b.components[k].get("ports") or (), key=_enc))[:limit]
    out["registers"] = _dict_diff(regs_old, regs_new, limit)
    out["memories"] = _dict_diff(a.memories, b.memories, limit)
    out["signals"] = sigs
    if connections:
        ca, cb = a.connections(), b.connections()
        added = sorted(cb - ca)
        removed = sorted(ca - cb)
        out["connections"] = {"added": [{"src": s, "dst": d, "kind": k} for s, d, k in added[:limit]],
                              "removed": [{"src": s, "dst": d, "kind": k} for s, d, k in removed[:limit]],
                              "counts": {"added": len(added), "removed": len(removed), "old_total": len(ca), "new_total": len(cb)}}
    aa, ab = a.assignments(), b.assignments()
    changed = []
    # An analog/inout port may gain its first driver or lose its last one.
    # A target absent on one side has no assignments on that side.
    for k in sorted(set(aa) | set(ab)):
        old_assigns, new_assigns = aa.get(k, []), ab.get(k, [])
        if [x[1] for x in old_assigns] != [x[1] for x in new_assigns]:
            c = {"path": k, "old": [x[0] for x in old_assigns[:10]], "new": [x[0] for x in new_assigns[:10]]}
            if c["old"] == c["new"]:
                c["note"] = ("same text, different typed expression (signedness, casts, widths, resizes, the "
                             "logic of a compiler temporary it reads, such as a mux result, or the reset value, "
                             "clock domain or logic of a generated register it reads, such as `RegNext(x) init k`); "
                             "see the `key` column of `assignments`")
                c["old_keys"] = [x[1] for x in aa[k][:10]]
                c["new_keys"] = [x[1] for x in ab[k][:10]]
                to, tn = a.temporaries_of(k), b.temporaries_of(k)
                if to != tn:
                    c["old_temporaries"], c["new_temporaries"] = to, tn
            go, gn = a.generated.get(k, []), b.generated.get(k, [])
            if go != gn:
                c["old_generated"], c["new_generated"] = go[:20], gn[:20]
            if k in a.incomplete or k in b.incomplete:
                c["incomplete"] = ("a typed key is incomplete (SpinalDB reached its expansion bound or cut a "
                                   "combinational loop): the change may be in the key only")
            changed.append(c)
    out["assignments"] = {"changed": changed[:limit], "counts": {"changed": len(changed)}}
    # Equal comparisons that rest on an incomplete key prove nothing: the diff is undetermined there.
    changed_paths = {c["path"] for c in changed} | {c["path"] for c in sigs["changed"]} | \
        {c["path"] for c in out["memories"]["changed"]}
    changed_paths |= {c["path"] for c in out["components"]["changed"]}
    # Incomplete internal declarations and assignments stay relevant even when their generated
    # names are absent from the comparison maps. They must never disappear with those names.
    undetermined = sorted((a.incomplete | b.incomplete) - changed_paths)
    if config_incomplete and not config_changed:
        undetermined.append("<emission_config>")
    if capture_incomplete:
        undetermined.append("<input_capture>")
    out["undetermined"] = {"paths": undetermined[:limit], "count": len(undetermined),
                           "reason": ("typed keys SpinalDB could not make complete (`$incomplete:`, `h!:`): a "
                                      "construct the keys do not model (a node class, statement, tag or field), a "
                                      "BlackBox without a fingerprinted body, a cut loop; equal keys there do not show "
                                      "equal hardware") if undetermined else None}
    s = out
    out["summary"] = {
        "components": s["components"]["counts"], "ports": s["ports"]["counts"], "registers": s["registers"]["counts"],
        "memories": s["memories"]["counts"], "signals": s["signals"]["counts"],
        "connections": s.get("connections", {}).get("counts"), "assignments": s["assignments"]["counts"],
        "undetermined": len(undetermined),
        "emission_config": config_changed,
        "identical": not config_changed and all(not any(v.values()) for k, v in (
            ("c", s["components"]["counts"]), ("s", s["signals"]["counts"]), ("m", s["memories"]["counts"]),
            ("a", s["assignments"]["counts"]))) and (not connections or not (s["connections"]["counts"]["added"] or
                                                                             s["connections"]["counts"]["removed"])),
    }
    if out["summary"]["identical"] and undetermined:
        out["summary"]["identical"] = None  # no difference found, but not shown equal either
    if capture_incomplete:
        out["summary"]["identical"] = None
        out.update(status="inconclusive", cause="input_not_captured:database_inputs:" + ",".join(capture_incomplete))
    out["input_capture"] = {"old": old.capture_record(), "new": new.capture_record()}
    return out


def diff_files(old, new, **kw) -> dict:
    """Compare two captured files and close both databases on every exit path."""
    a = DesignDB(old)
    try:
        b = DesignDB(new, capture=a.capture)
        try:
            result = diff(a, b, **kw)
            stale = [f"new database: {w}" for w in b.staleness()]
            if stale:
                result["db_warnings"] = stale
            return result
        finally:
            b.close()
    finally:
        a.close()
