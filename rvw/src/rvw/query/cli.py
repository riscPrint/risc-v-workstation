"""`rvw query`: questions about an elaborated design, answered from a SpinalDB design database."""
from __future__ import annotations

import argparse
import json
import sys

from . import diff as diff_mod
from . import ops
from .db import QueryError, default_db, run_on


def register(subparsers) -> None:
    p = subparsers.add_parser("query", help="query a SpinalDB design database (drivers, loads, paths, diff, ...)",
                              description=__doc__)
    sub = p.add_subparsers(dest="query_command", required=True)

    def cmd(name, help_, func, db=True):
        c = sub.add_parser(name, help=help_)
        if db:
            c.add_argument("--db", default=None, help="design database (default: $RVW_DESIGNDB or ./design.db)")
        c.add_argument("--json", action="store_true", help="machine-readable output")
        c.set_defaults(func=lambda a: _run(a, func))
        return c

    build = sub.add_parser("build", help="build the selected project's design database")
    build.add_argument("--config", help="core preset (default core.default_config)")
    build.add_argument("--out", help="database output (default query.db)")
    build.add_argument("--json", action="store_true")
    build.set_defaults(func=_build)

    hdl = sub.add_parser("build-hdl", help="build a navigation database from Verilog or the Yosys SV subset")
    hdl.add_argument("sources", nargs="+")
    hdl.add_argument("--top", required=True)
    hdl.add_argument("--out", required=True)
    hdl.add_argument("--yosys", default="yosys")
    hdl.add_argument("--timeout", type=int, default=120)
    hdl.add_argument("--json", action="store_true")
    hdl.set_defaults(func=lambda a: _run(a, lambda d, a: _build_hdl(a)))

    c = cmd("info", "what the database holds", lambda d, a: ops.info(d))

    c = cmd("where", "Scala source, Verilog name and waveform path of a signal", lambda d, a: ops.where(d, a.signal))
    c.add_argument("signal")

    c = cmd("drivers", "what drives a signal: assignments, conditions, enables, reset", lambda d, a: ops.drivers(d, a.signal))
    c.add_argument("signal")

    c = cmd("loads", "what reads a signal", lambda d, a: ops.loads(d, a.signal, limit=a.limit))
    c.add_argument("signal")
    c.add_argument("--limit", type=int, default=500)

    for name, f in (("fanin", ops.fanin), ("fanout", ops.fanout)):
        c = cmd(name, f"{'transitive drivers' if name == 'fanin' else 'transitive readers'} of a signal or interface",
                lambda d, a, f=f: f(d, a.signal, depth=a.depth, stop_at_regs=a.stop_at_regs,
                                    kinds=a.kind or None, limit=a.limit, include_clock=a.include_clock))
        c.add_argument("signal")
        c.add_argument("--depth", type=int, default=1)
        c.add_argument("--stop-at-regs", action="store_true", help="do not expand past registers, memories or synchronous read state")
        c.add_argument("--kind", action="append", choices=sorted(ops.KIND_RANK), help="only these dependency kinds")
        c.add_argument("--limit", type=int, default=500, help="maximum signals")
        c.add_argument("--include-clock", action="store_true", help="include explicit clock-domain relations when stored; keep data uses in all cases")

    c = cmd("path", "registers and logic between two signals or interfaces (A drives ... B)",
            lambda d, a: ops.path(d, a.a, a.b, comb_only=a.comb_only, data_only=a.data_only, max_paths=a.max_paths))
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--comb-only", action="store_true", help="only combinational paths (stop at registers, memories and synchronous read state)")
    c.add_argument("--data-only", action="store_true", help="ignore control dependencies (conditions, selects)")
    c.add_argument("--max-paths", type=int, default=3)

    c = cmd("search", "find signals and components by name (glob, substring or --regex)",
            lambda d, a: ops.search(d, a.pattern, kind=a.kind, regex=a.regex, scope=a.scope,
                                    include_generated=a.include_generated, limit=a.limit))
    c.add_argument("pattern")
    c.add_argument("--kind", choices=["reg", "wire", "port", "mem", "component"])
    c.add_argument("--regex", action="store_true")
    c.add_argument("--scope", help="only inside this component")
    c.add_argument("--include-generated", action="store_true", help="include compiler temporaries (_zz_*, when_*)")
    c.add_argument("--limit", type=int, default=100)

    c = cmd("hierarchy", "component tree", lambda d, a: ops.hierarchy(d, a.path, depth=a.depth))
    c.add_argument("path", nargs="?")
    c.add_argument("--depth", type=int, default=2)

    c = cmd("component", "ports, interfaces, children, registers, memories and Areas of a component",
            lambda d, a: ops.component(d, a.path))
    c.add_argument("path", nargs="?")

    c = cmd("regs", "registers of a component", lambda d, a: ops.regs(d, a.path, recursive=a.recursive,
                                                                       include_generated=a.include_generated))
    c.add_argument("path", nargs="?")
    c.add_argument("-r", "--recursive", action="store_true")
    c.add_argument("--include-generated", action="store_true")

    c = cmd("export", "write an artifact stored in the database (blocks, pdg, hgldd) to a file",
            lambda d, a: ops.export(d, a.artifact, a.out))
    c.add_argument("artifact")
    c.add_argument("out")

    c = cmd("diff", "what changed in the elaborated hardware between two databases", _diff, db=False)
    c.add_argument("old")
    c.add_argument("new")
    c.add_argument("--scope", help="only inside this component")
    c.add_argument("--limit", type=int, default=200, help="maximum entries per category")
    c.add_argument("--no-connections", action="store_true", help="skip the (slower) connection graph comparison")


def _diff(_db, a):
    return diff_mod.diff_files(a.old, a.new, scope=a.scope, limit=a.limit, connections=not a.no_connections)


def _run(args: argparse.Namespace, func) -> int:
    try:
        from rvw.common.project import database
        if hasattr(args, "db"):
            selected_db, project_capture = database(args.db, getattr(args, "project", None))
            result = run_on(selected_db or default_db(), lambda db: func(db, args))
            if project_capture is not None:
                result["project_capture"] = project_capture
        else:
            result = func(None, args)
    except (QueryError, ValueError, OSError) as e:
        if args.json:
            print(json.dumps(e.to_json() if isinstance(e, QueryError) else {"error": str(e)}, indent=1))
        else:
            print(f"error: {e}", file=sys.stderr)
            for c in getattr(e, "candidates", []):
                print(f"  {c}", file=sys.stderr)
        return 2
    stale = result.get("db_warnings", []) if isinstance(result, dict) else []
    for w in stale:
        print(f"warning: {w}", file=sys.stderr)
    if args.json:
        print(json.dumps(result, indent=1, default=list))
    else:
        print(render(args.query_command, result))
    return 0


# ------------------------------------------------------------------------------------------------ text
def _show(v) -> str:
    """A diff value as text: a string as it is, a structured value (dict, list) as compact JSON."""
    return v if isinstance(v, str) or v is None else json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _sig_line(s: dict) -> str:
    bits = [s["path"], s["kind"]]
    if s.get("direction"):
        bits.append(s["direction"])
    bits.append(f"{s.get('type')}[{s.get('width')}]")
    return " ".join(bits)


def render(command: str, r: dict) -> str:
    out: list[str] = []
    w = out.append
    if r.get("status") == "inconclusive":
        w(f"inconclusive: {r.get('cause', 'input_not_captured')}")
    if command in ("where", "drivers", "loads") and "signal" in r:
        s = r["signal"]
        w(_sig_line(s))
        if command == "where":
            w(f"  spinal   {s.get('spinal_path')}" + (f"  ({s['data_type']})" if s.get("data_type") else ""))
            if "verilog" in s:
                v = s["verilog"]
                w(f"  verilog  {v['module']}.{v['name']}" + (f"  at {v['loc']}" if v.get('loc') else ""))
            if s.get("wave"):
                w(f"  wave     {s['wave']}")
            if s.get("origin"):
                w(f"  origin   {s['origin']}")
            w(f"  scala    {s.get('loc')}")
            if s.get("area"):
                w(f"  area     {s['area']}")
            if s.get("clock_domain"):
                w(f"  clock    {s['clock_domain']}  reset value {s.get('reset_value')}")
        else:
            w(f"  scala {s.get('loc')}")
    if command == "where" and r.get("group"):
        b = r.get("bundle")
        if b:
            w(f"{b['path']}: {b['type']} {b['direction']}, {b['signals']} signals, {b['bits']} bits, declared at {b['loc']}")
        w(f"{r['count']} signals in {r['query']}:")
        for s in r["signals"]:
            w(f"  {_sig_line(s)}")
    elif command == "where":
        pass  # printed above
    elif command == "drivers":
        reg = r.get("register")
        if reg:
            rst = reg.get("reset")
            w(f"  register on {reg['clock']} ({reg['edge']})" +
              (f", reset {rst['signal']} ({rst['kind']}, active {rst['active']}) to {rst['value']}" if rst else ", no reset") +
              (f", clock enable {reg['clock_enable']}" if reg.get("clock_enable") else ""))
        if r.get("origin"):
            w(f"  {r['origin']}")
        for a in r["assignments"]:
            w(f"  {'initial ' if a.get('kind') == 'initial' else ''}{a.get('range') or ''}:= {a['source']}" + (f"   [enable {a['enable']}]" if a.get("enable") else "") +
              (f"   [mask {a['mask']}]" if a.get("mask") else ""))
            if a.get("condition"):
                w(f"      under {a['condition']}")
            w(f"      at {a['loc']}" + (f" (in {a['in_component']})" if a.get("in_component") else ""))
        if r.get("memory"):
            m = r["memory"]
            w(f"  memory {m['depth']} x {m['width']} bits" +
              (f", initialized ({m['init']['words']} words, sha256 {m['init']['sha256'][:12]})" if m.get("init") else ""))
            for p in m["ports"]:
                w(f"    {p['kind']} addr {p['address']}" + (f" data {p['data']}" if p.get("data") else "") +
                  (f" en {p['enable']}" if p.get("enable") else "") + (f" wen {p['write_enable']}" if p.get("write_enable") else "") +
                  f"  at {p['loc']}")
        if r.get("note"):
            w(f"  note: {r['note']}")
        if r["read_signals"]:
            w("  reads: " + ", ".join(f"{x['path']} ({'+'.join(x['kinds'])})" for x in r["read_signals"]))
    elif command == "loads":
        w(f"  {r['reader_count']} readers")
        for x in r["readers"]:
            w(f"    {x['path']}  {x['signal_kind']} via {'+'.join(x['kinds'])}")
        for a in r["statements"]:
            w(f"  {a['target']} {'initial ' if a.get('kind') == 'initial' else ''}{a.get('range') or ''}:= {a['source']}   "
              f"({'/'.join(a['read_as'])})" +
              (f"  when {a['condition']}" if a.get("condition") else "") + f"  at {a['loc']}")
        for c in r["conditions"]:
            w(f"  condition {c['condition']} guards {c['guarded_assignments']} assignments  at {c['loc']}")
    elif command in ("fanin", "fanout"):
        w(f"{r['direction']} of {', '.join(r['start'][:5])}{' ...' if len(r['start']) > 5 else ''} (depth {r['depth']})")
        for n in r["nodes"]:
            w(f"  {'  ' * (n['depth'] - 1)}{n['depth']} {_sig_line(n)}  {n.get('loc') or ''}")
        if r["truncated"]:
            w("  (truncated: raise --limit)")
    elif command == "path":
        if not r["found"]:
            w(f"no path from {r['from'][:3]} to {r['to'][:3]} ({r.get('hint')})")
        for i, p in enumerate(r.get("paths", [])):
            w(f"path {i + 1}: {p['length']} hops, {p['register_stages']} register stages")
            for h in p["hops"]:
                w(f"  {'-' + h['via'] + '-> ' if h.get('via') else ''}{_sig_line(h)}")
                for l in h.get("logic", [])[:2]:
                    w(f"        {l.get('range') or ''}:= {l.get('source')}" + (f"  when {l['condition']}" if l.get("condition") else "") +
                      f"  at {l.get('loc')}")
    elif command == "search":
        for m in r["matches"]:
            w(f"component {m['component']} ({m['module']}, {m['class']})" if "component" in m else _sig_line(m))
        w(f"{r['total']} matches" + (" (truncated)" if r["truncated"] else ""))
    elif command == "hierarchy":
        def node(n, d):
            w(f"{'  ' * d}{n['name']}: {n['module']} ({n['class']})" + (f" +{n['children_count']} children" if n.get("children_count") else ""))
            for c in n.get("children", []):
                node(c, d + 1)
        node(r["root"], 0)
    elif command == "component":
        w(f"{r['component']}: module {r['module']}, class {r['class']}, {r['loc']}")
        w(f"  counts {r['counts']}")
        if r["interfaces"]:
            w("  interfaces:")
            for i in r["interfaces"]:
                w(f"    {i['interface']}: {i['type']} {i['direction']}, {i['signals']} signals, {i['bits']} bits")
        w("  ports:")
        for p in r["ports"]:
            w(f"    {p['direction']:5} {p['spinal']} {p['type']}[{p['width']}]")
        if r["children"]:
            w("  children: " + ", ".join(f"{c['name']} ({c['module']})" for c in r["children"]))
        for a in r["areas"]:
            w(f"  area {a['area']} ({a['class']}): {a['signals']} signals, {a['registers']} registers")
        for g in r["registers"]:
            w(f"  reg {g['path']} {g['type']}[{g['width']}] reset {g['reset_value']}")
        for m in r["memories"]:
            w(f"  mem {m['name']} {m['depth']}x{m['width']} ports {m['ports']}")
    elif command == "regs":
        for g in r["registers"]:
            w(f"{g['path']} {g['type']}[{g['width']}] reset {g['reset_value']}  {g['loc']}")
        w(f"{r['count']} registers, {r['bits']} bits")
    elif command == "diff":
        w(f"old {r['old']['db']}  new {r['new']['db']}")
        w(f"summary: {json.dumps(r['summary'])}")
        if r["emission_config"]["changed"]:
            w("~ emission configuration")
            w("  - " + _show(r["emission_config"]["old"]))
            w("  + " + _show(r["emission_config"]["new"]))
        for cat in ("components", "ports", "registers", "memories", "signals"):
            d = r[cat]
            for a in d["added"]:
                w(f"  + {cat[:-1]} {a['path']}")
            for a in d["removed"]:
                w(f"  - {cat[:-1]} {a['path']}")
            for c in d["changed"]:
                w(f"  ~ {cat[:-1]} {c['path']}: " + ", ".join(f"{k} {_show(v['old'])} -> {_show(v['new'])}"
                                                             for k, v in c["changes"].items()))
        for p in r["ports"].get("reordered", []):
            w(f"  ~ port order of {p}")
        if "connections" in r:
            for c in r["connections"]["added"]:
                w(f"  + connection {c['src']} -> {c['dst']} ({c['kind']})")
            for c in r["connections"]["removed"]:
                w(f"  - connection {c['src']} -> {c['dst']} ({c['kind']})")
        for c in r["assignments"]["changed"]:
            w(f"  ~ logic of {c['path']}" + (f"  ({c['note']})" if c.get("note") else ""))
            for o in c["old"]:
                w(f"      - {o}")
            for n in c["new"]:
                w(f"      + {n}")
            for o in c.get("old_temporaries", []):
                w(f"      - (temporary) {o}")
            for n in c.get("new_temporaries", []):
                w(f"      + (temporary) {n}")
            for o in c.get("old_generated", []):
                w(f"      - (generated register) {_show(o)}")
            for n in c.get("new_generated", []):
                w(f"      + (generated register) {_show(n)}")
        u = r.get("undetermined") or {}
        if u.get("count"):
            w(f"  ? undetermined ({u['reason']}): " + ", ".join(u["paths"]) +
              (f" (+{u['count'] - len(u['paths'])} more)" if u["count"] > len(u["paths"]) else ""))
    elif command == "info":
        m = r["meta"]
        w(f"{r['db']} ({r['size_bytes'] // (1 << 20)} MB), schema {m.get('schema')}, created {m.get('created')}")
        w(f"  toplevel {m.get('toplevel')} ({m.get('toplevel_class')})" +
          (f", {m['core']} {m.get('config')} at {m.get('core_rev')}{' (dirty)' if m.get('core_dirty') == 'true' else ''}" if m.get("core") else ""))
        w("  " + ", ".join(f"{k} {v}" for k, v in r["counts"].items()))
        for cd in r["clock_domains"]:
            w(f"  clock domain {cd}")
        w("  artifacts: " + ", ".join(f"{a['name']} ({a['size'] // 1024} KiB)" for a in r["artifacts"]))
        w("  rtl: " + ", ".join(r["rtl_files"]))
        if r["warnings"]:
            w(f"  {len(r['warnings'])} warnings (first: {r['warnings'][0]})")
    elif command == "export":
        w(f"wrote {r['artifact']} to {r['out']} ({r['bytes']} bytes)")
    else:
        w(json.dumps(r, indent=1, default=list))
    return "\n".join(out)


def _build(args):
    from .project import build_database
    try:
        result = build_database(getattr(args, "project", None), args.config, args.out)
    except (ValueError, OSError, QueryError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, default=str) if args.json else render("info", result))
    return 0


def _build_hdl(args):
    from .hdl import build_hdl
    return build_hdl(args.sources, args.top, args.out, yosys=args.yosys, timeout=args.timeout)
