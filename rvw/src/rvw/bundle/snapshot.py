"""Pipeline-state snapshot from a waveform, driven by the core's debug description.

A snapshot group (one `[[snapshot]]` table in the core config):

    name   = "Load queue"
    unit   = "LSU"
    scope  = 'tile\\.lsu_1\\.'          # regex; fields are matched against the rest of the name
    values = { head = 'ldq_head', tail = 'ldq_tail' }          # value of one signal each
    enums  = { state = ["reset", "normal", ...] }               # optional value labels
    counts = { valid = 'ldq_valid_\\d+' }                       # how many 1-bit signals are 1
    busy   = { mshrs = { pattern = 'mshrs_\\d+\\.state', idle = 0 } }   # how many are != idle
    [snapshot.table]                                           # one row per entry
    key     = 'ldq_valid_(\\d+)'        # rows: entries whose key signal is 1
                                       #   (idle = N: key != N instead; all = true: every entry)
    columns = { executed = 'ldq_executed_(\\d+)', pc = 'ldq_uop_(\\d+)_debug_pc' }

Patterns are Python regexes that must match the whole remainder after `scope`. Table patterns
have one group, the entry index.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..wave import vcd


@dataclass
class _Field:
    group: int
    kind: str           # value, count, busy, key, col
    name: str
    vars: list          # [(index or None, Var)]
    idle: int = 0


def _compile(groups: list[dict], hdr: vcd.Header) -> list[_Field]:
    fields: list[_Field] = []
    for gi, g in enumerate(groups):
        srx = re.compile(g.get("scope", ""))
        cand = []
        for v in hdr.vars:
            m = srx.search(v.name)
            if m:
                cand.append((v.name[m.end():], v))

        def resolve(pat: str, indexed: bool):
            rx = re.compile(pat)
            out, seen = [], set()
            for rest, v in cand:
                m = rx.fullmatch(rest)
                if m:
                    idx = int(m.group(1)) if indexed and m.groups() else None
                    key = (idx, rest)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append((idx, v))
            # Prefer the shallowest path for single values (aliases appear at several levels)
            out.sort(key=lambda iv: ((iv[0] if iv[0] is not None else -1), iv[1].name.count(".")))
            return out

        for k, pat in (g.get("values") or {}).items():
            vs = resolve(pat, False)
            fields.append(_Field(gi, "value", k, vs[:1]))
        for k, pat in (g.get("counts") or {}).items():
            fields.append(_Field(gi, "count", k, resolve(pat, False)))
        for k, spec in (g.get("busy") or {}).items():
            fields.append(_Field(gi, "busy", k, resolve(spec["pattern"], False), int(spec.get("idle", 0))))
        t = g.get("table")
        if t:
            fields.append(_Field(gi, "key", t["key"], resolve(t["key"], True)))
            for k, pat in (t.get("columns") or {}).items():
                fields.append(_Field(gi, "col", k, resolve(pat, True)))
    return fields


def take(groups: list[dict], wave: str, t: int) -> list[dict]:
    """Evaluate the snapshot groups at time `t` of `wave` (one streaming pass)."""
    with vcd.open_text(wave) as f:
        hdr = vcd.read_header(f)
        fields = _compile(groups, hdr)
        codes = {v.code for fl in fields for _, v in fl.vars}
        vals, _ = vcd.state_at(f, t, codes)
    return evaluate(groups, fields, vals)


def evaluate(groups: list[dict], fields: list[_Field], vals: dict[str, str]) -> list[dict]:
    out = []
    for gi, g in enumerate(groups):
        res = {"name": g.get("name", f"group{gi}"), "unit": g.get("unit"), "values": {}, "counts": {},
               "missing": []}
        enums = g.get("enums") or {}
        key = None
        cols = []
        for fl in (x for x in fields if x.group == gi):
            if not fl.vars:
                res["missing"].append(fl.name)
                continue
            if fl.kind == "value":
                v = fl.vars[0][1]
                raw = vals.get(v.code)
                n = vcd.to_int(raw)
                s = vcd.fmt_value(raw, v.width) if raw is not None else "?"
                if n is not None and fl.name in enums and n < len(enums[fl.name]):
                    s = f"{s} ({enums[fl.name][n]})"
                res["values"][fl.name] = s
            elif fl.kind == "count":
                ns = [vcd.to_int(vals.get(v.code)) for _, v in fl.vars]
                ones = "?" if None in ns else sum(n == 1 for n in ns)
                res["counts"][fl.name] = f"{ones}/{len(fl.vars)}"
            elif fl.kind == "busy":
                ns = [vcd.to_int(vals.get(v.code)) for _, v in fl.vars]
                busy = "?" if None in ns else sum(n != fl.idle for n in ns)
                res["counts"][fl.name] = f"{busy}/{len(fl.vars)}"
            elif fl.kind == "key":
                key = fl
            elif fl.kind == "col":
                cols.append(fl)
        if key is not None:
            t = g["table"]
            show_all = bool(t.get("all"))
            idle = t.get("idle")
            rows = []
            unknown = []
            colmap = {c.name: {i: v for i, v in c.vars} for c in cols}
            for i, kv in key.vars:
                raw = vals.get(kv.code)
                n = vcd.to_int(raw)
                if n is None:
                    unknown.append({"#": i, "value": vcd.fmt_value(raw, kv.width) if raw else "?"})
                on = n is not None and (n != int(idle) if idle is not None else n == 1)
                if not (on or show_all):
                    continue
                row = {"#": i}
                for c in cols:
                    v = colmap[c.name].get(i)
                    raw = vals.get(v.code) if v else None
                    row[c.name] = vcd.fmt_value(raw, v.width) if raw is not None else "?"
                rows.append(row)
            res["table"] = {"columns": ["#"] + [c.name for c in cols], "rows": rows,
                            "entries": len(key.vars)}
            if unknown:
                res["table"]["unknown_entries"] = unknown
        out.append(res)
    return out


def render_md(snap: list[dict]) -> str:
    lines = []
    for g in snap:
        head = f"**{g['name']}**" + (f" ({g['unit']})" if g.get("unit") else "")
        kv = [f"{k}={v}" for k, v in g["values"].items()] + [f"{k}={v}" for k, v in g["counts"].items()]
        lines.append(f"- {head}: " + (", ".join(kv) if kv else ""))
        if g.get("missing"):
            lines.append(f"  - not in wave: {', '.join(g['missing'])}")
        t = g.get("table")
        if t:
            if t.get("unknown_entries"):
                lines.append("  - unknown entry keys: " + ", ".join(
                    f"{r['#']}={r['value']}" for r in t["unknown_entries"]))
            if not t["rows"]:
                qualifier = "known " if t.get("unknown_entries") else ""
                lines.append(f"  - no {qualifier}live entries (of {t['entries']})")
            else:
                lines.append("")
                lines.append("  | " + " | ".join(t["columns"]) + " |")
                lines.append("  |" + "---|" * len(t["columns"]))
                for r in t["rows"]:
                    lines.append("  | " + " | ".join(str(r.get(c, "")) for c in t["columns"]) + " |")
                lines.append("")
    return "\n".join(lines)
