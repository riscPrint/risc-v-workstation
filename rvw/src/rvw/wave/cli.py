"""`rvw wave`: query value changes, list signals, sample at a time, cut a time window."""
from __future__ import annotations

import argparse
import sys

from ..common import jsonout
from . import ops
from .capture import wave_input
from ..common.capture import CaptureError
from .vcd import WaveError

TIME_HELP = "time in wave units, or 'Nc' for cycle N (period from --period or the clock)"


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("wave", help="query and cut VCD/FST waveforms or indexed snapshots",
                       description=__doc__)
    w = p.add_subparsers(dest="wave_cmd", required=True)

    q = w.add_parser("index", help="build an identity-bound SQLite waveform snapshot")
    q.add_argument("wave")
    q.add_argument("-o", "--out", required=True)
    q.add_argument("--reader", choices=["auto", "vcd", "wellen"], default="auto",
                   help="vcd: strict VCD text reader (FST via fst2vcd); wellen: wellen library, "
                        "FST read natively; auto: wellen for FST when pywellen is installed")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=_index)

    q = w.add_parser("verify", help="check an index against its source wave by full SHA-256")
    q.add_argument("index")
    q.add_argument("--source", help="wave to compare (default: the path recorded in the index)")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=_verify)

    def common(q, regex=True, regex_required=True):
        q.add_argument("wave", help=".vcd, .vcd.gz, .fst or .rvwi")
        if regex:
            q.add_argument("regex", nargs=None if regex_required else "?",
                           help="Python regex searched in dotted signal paths (TOP.Top.unit.sig)")
        q.add_argument("--json", action="store_true", help="JSON output")
        q.add_argument("--period", type=int, help="clock period in wave time units (for 'Nc')")
        q.add_argument("--clock", default=ops.CLOCK_RX, help="clock signal regex for period detection")
        q.add_argument("--indexed", action="store_true",
                       help="query a cached index of the wave (RVW_WAVE_INDEX_DIR); built on first "
                            "use and rebuilt when the wave's size or mtime changes")

    q = w.add_parser("list", help="list signals (name and width)")
    common(q, regex_required=False)
    q.set_defaults(func=_list)

    q = w.add_parser("changes", help="print value changes of matching signals")
    common(q)
    q.add_argument("--from", dest="t0", help=TIME_HELP)
    q.add_argument("--to", dest="t1", help=TIME_HELP)
    q.add_argument("--limit", type=int, default=ops.DEFAULT_CHANGES_LIMIT,
                   help=f"stop after N changes (default {ops.DEFAULT_CHANGES_LIMIT}; 0 = no limit). "
                        "JSON output says whether the result was truncated")
    q.add_argument("--dec", action="store_true", help="decimal instead of hex")
    q.add_argument("--db", help="SpinalDB design database: show and compare Spinal enum element names")
    q.set_defaults(func=_changes)

    q = w.add_parser("sample", help="value of matching signals at one time")
    common(q)
    q.add_argument("--at", required=True, help=TIME_HELP + "; 'end' for the last timestamp")
    q.add_argument("--dec", action="store_true", help="decimal instead of hex")
    q.add_argument("--db", help="SpinalDB design database: show and compare Spinal enum element names")
    q.set_defaults(func=_sample)

    q = w.add_parser("cut", help="write a time window (and optionally a signal subset) to a new file")
    common(q, regex=False)
    q.add_argument("--from", dest="t0", required=True, help=TIME_HELP)
    q.add_argument("--to", dest="t1", help=TIME_HELP + " (default: end)")
    q.add_argument("--signals", help="keep only signals matching this regex")
    q.add_argument("--rebase", action="store_true", help="shift times so the window starts at 0")
    q.add_argument("-o", "--out", required=True, help="output .vcd, .vcd.gz, .fst or .rvwi")
    q.set_defaults(func=_cut)

    q = w.add_parser("find", help="times where an expression over signals holds (first, last, intervals)")
    common(q, regex=False)
    q.add_argument("expr", help="expression, e.g. 'valid && ready && data[7:0] == 0x2a', 'rose(clk)'")
    q.add_argument("--from", dest="t0", help=TIME_HELP)
    q.add_argument("--to", dest="t1", help=TIME_HELP)
    q.add_argument("--limit", type=int, default=1000, help="intervals to list (default 1000; 0 = all)")
    q.add_argument("--db", help="SpinalDB design database: show and compare Spinal enum element names")
    q.set_defaults(func=_find)

    q = w.add_parser("edges", help="value changes, rising and falling edges per signal in a window")
    common(q)
    q.add_argument("--from", dest="t0", help=TIME_HELP)
    q.add_argument("--to", dest="t1", help=TIME_HELP)
    q.set_defaults(func=_edges)

    q = w.add_parser("why", help="why a signal has its value at T: active drivers from a design database")
    common(q, regex=False)
    q.add_argument("signal", help="signal name (Verilog, waveform or Spinal path)")
    q.add_argument("--at", required=True, help=TIME_HELP)
    q.add_argument("--db", help="SpinalDB design database (default: RVW_DESIGNDB)")
    q.add_argument("--depth", type=int, default=2, help="levels of read signals to follow (default 2)")
    q.add_argument("--max-nodes", type=int, default=64, help="stop after N explained signals (default 64)")
    q.set_defaults(func=_why)

    q = w.add_parser("seq", help="match a clocked sequence 'a ##1 b ##[1:3] c' at every edge where a holds")
    common(q, regex=False)
    q.add_argument("sequence", help="expressions joined by ##N or ##[lo:hi] (hi may be $) clock delays")
    q.add_argument("--from", dest="t0", help=TIME_HELP)
    q.add_argument("--to", dest="t1", help=TIME_HELP)
    q.add_argument("--limit", type=int, default=100, help="matches and failures to list (default 100; 0 = all)")
    q.add_argument("--db", help="SpinalDB design database: show and compare Spinal enum element names")
    q.set_defaults(func=_seq)

    q = w.add_parser("txn", help="handshake transfers, stalls and protocol issues of a Stream or Flow")
    common(q, regex=False)
    q.add_argument("--valid", help="valid signal name")
    q.add_argument("--ready", help="ready signal name (omit for a Flow)")
    q.add_argument("--payload", help="payload signals regex")
    q.add_argument("--stream", help="Stream/Flow bundle path in the design database (sets valid/ready/payload)")
    q.add_argument("--db", help="SpinalDB design database for --stream (default: RVW_DESIGNDB)")
    q.add_argument("--from", dest="t0", help=TIME_HELP)
    q.add_argument("--to", dest="t1", help=TIME_HELP)
    q.add_argument("--limit", type=int, default=1000, help="transfers and issues to list (default 1000; 0 = all)")
    q.set_defaults(func=_txn)

    q = w.add_parser("diff", help="compare two waves and report the first divergence")
    common(q, regex=False)
    q.add_argument("other", help="second wave (B)")
    q.add_argument("--signals", help="compare only signals matching this regex (names in A)")
    q.add_argument("--from", dest="t0", help=TIME_HELP + " (in A)")
    q.add_argument("--to", dest="t1", help=TIME_HELP + " (in A)")
    q.add_argument("--offset", type=int, default=0, help="B time = A time + OFFSET")
    q.add_argument("--map", help="A_PREFIX=B_PREFIX: rename A signal prefixes to find B signals")
    q.add_argument("--on-clock", action="store_true", help="sample both at A's rising clock edges (--clock)")
    q.add_argument("--all", action="store_true", help="scan the whole window; report each signal's first divergence")
    q.add_argument("--align", help="compare the k-th clock edge where this expression holds in A and B "
                                   "(e.g. a commit valid) instead of equal times")
    q.add_argument("--align-b", help="the event expression in B, when B names it differently")
    q.add_argument("--limit", type=int, default=50, help="signals to list (default 50)")
    q.set_defaults(func=_diff)

    q = w.add_parser("session", help="save or open a portable debug session (signals, cursors, queries, artifacts)")
    ss = q.add_subparsers(dest="session_cmd", required=True)
    q = ss.add_parser("save", help="write a session file bound to artifact SHA-256 hashes")
    q.add_argument("out")
    q.add_argument("--wave", required=True)
    q.add_argument("--db", help="design database to bind")
    q.add_argument("--signal", action="append", default=[], help="signal regex to keep (repeat)")
    q.add_argument("--cursor", action="append", type=int, default=[], help="cursor time (repeat)")
    q.add_argument("--query", action="append", default=[], help="saved *.rvwq.json query to embed (repeat)")
    q.add_argument("--artifact", action="append", default=[], help="another file to bind (repeat)")
    q.add_argument("--note")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=_session_save)
    q = ss.add_parser("open", help="locate and verify a session's artifacts; report missing or changed ones")
    q.add_argument("session")
    q.add_argument("--root", help="directory to search for moved artifacts")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=_session_open)

    q = w.add_parser("value", help="typed value of a signal, Bundle, Stream, Vec or Area at T (needs --db)")
    common(q, regex=False)
    q.add_argument("name", help="signal or Bundle/Area path in the design database")
    q.add_argument("--at", required=True, help=TIME_HELP + "; 'end' for the last timestamp")
    q.add_argument("--db", help="SpinalDB design database (default: RVW_DESIGNDB)")
    q.add_argument("--dec", action="store_true", help="decimal instead of hex")
    q.set_defaults(func=_value)

    q = w.add_parser("bench", help="run a debug task file (rvw.debug-tasks/1): time and check each rvw answer")
    q.add_argument("tasks")
    q.add_argument("--var", action="append", default=[], help="NAME=VALUE for {NAME} in task argv (repeat)")
    q.add_argument("--task", action="append", help="run only this task id (repeat)")
    q.add_argument("--timeout", type=float, default=600)
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=_bench)

    q = w.add_parser("info", help="timescale, signal count, first/last time, clock period")
    common(q, regex=False)
    q.set_defaults(func=_info)


def time_at(wave, s, period=None, clock=ops.CLOCK_RX):
    """Resolve CLI/MCP time strings, detecting a clock only for cycle notation."""
    if s is None:
        return None
    if s.strip().endswith(("c", "cycle", "cycles")):
        return ops.parse_time(s, period or ops.detect_period(wave, clock))
    return ops.parse_time(s, None)


def _t(a, s):
    return time_at(a.wave, s, a.period, a.clock)


def _wrap(fn):
    def run(a):
        try:
            if getattr(a, 'indexed', False):
                from .index import ensure
                a.wave = ensure(a.wave)
            original = a.wave
            if fn.__name__ == '_cut':
                import os
                if os.path.exists(a.out) and os.path.samefile(original, a.out):
                    raise WaveError(f'{a.out} is the input wave; cut to a different file')
            import contextlib
            import io
            output = io.StringIO()
            with contextlib.redirect_stdout(output), wave_input(original) as saved:
                a.wave = saved
                a.capture_source = original
                try:
                    result = fn(a)
                finally:
                    a.wave = original
            sys.stdout.write(output.getvalue())
            return result
        except WaveError as e:
            if a.json:
                jsonout.write({'error': str(e)})
            print(f"rvw wave: {e}", file=sys.stderr)
            return 2
        except (CaptureError, jsonout.JsonOutputError) as e:
            print(f"rvw wave: {e}", file=sys.stderr)
            return 2
        except BrokenPipeError:
            return 0
    return run


@_wrap
def _list(a):
    vs = ops.list_signals(a.wave, a.regex)
    if a.json:
        jsonout.write([{"name": v.name, "width": v.width, "kind": v.kind, "code": v.code} for v in vs],
                      indent=1)
    else:
        for v in vs:
            print(v.name, v.width)
    return 0


@_wrap
def _changes(a):
    page = ops.changes_page(a.wave, a.regex, _t(a, a.t0) or 0, _t(a, a.t1), a.limit,
                            "dec" if a.dec else "hex")
    if a.db:
        from .typed import annotate_changes, enums
        annotate_changes(page, enums(a.db))
    if a.json:
        jsonout.write(page)
    else:
        for r in page["changes"]:
            print(f"{r['time']:10d} {r['signal']} = {r['value']}" + (f" ({r['enum']})" if 'enum' in r else ""))
    if page["truncated"]:
        print(f"rvw wave: truncated at {page['limit']} changes; narrow --from/--to or the regex, "
              "or raise --limit (0 = no limit)", file=sys.stderr)
    return 0


@_wrap
def _sample(a):
    from .vcd import end_time
    t = end_time(a.wave) if a.at == "end" else _t(a, a.at)
    vals = ops.sample(a.wave, a.regex, t, "dec" if a.dec else "hex")
    names = {}
    if a.db:
        from .typed import annotate_sample, enums
        names = annotate_sample(vals, enums(a.db))
    if a.json:
        jsonout.write({"time": t, "values": vals, **({"enums": names} if a.db else {})}, indent=1)
    else:
        print(f"# t={t}")
        for k, v in vals.items():
            print(f"{k} = {v if v is not None else '?'}" + (f" ({names[k]})" if k in names else ""))
    return 0


@_wrap
def _cut(a):
    r = ops.cut(a.wave, a.out, _t(a, a.t0), _t(a, a.t1), a.signals, a.rebase)
    if a.json:
        jsonout.write(r)
    else:
        print(f"wrote {r['out']}: {r['signals']} signals, {r['changes']} changes, {r['bytes']} bytes")
    return 0


@_wrap
def _info(a):
    i = ops.info(a.wave, a.clock)
    d = {**i.__dict__, "path": a.capture_source}
    if a.json:
        jsonout.write(d)
    else:
        for k, v in d.items():
            print(f"{k}: {v}")
    return 0


@_wrap
def _find(a):
    from .search import find
    from .typed import enums
    r = find(a.wave, a.expr, _t(a, a.t0) or 0, _t(a, a.t1), a.limit, enums(a.db) if a.db else None)
    if a.json:
        jsonout.write(r)
    else:
        print(f"# {r['count']} intervals; first {r['first']}; signals "
              + ", ".join(f"{k}={v}" for k, v in r['signals'].items()))
        for m in r['matches']:
            print(f"{m['start']:10d} .. {m['end'] if m['end'] is not None else 'end'}")
    if r['truncated']:
        print(f"rvw wave: listed {r['limit']} of {r['count']} intervals", file=sys.stderr)
    return 0


@_wrap
def _edges(a):
    from .search import edges
    r = edges(a.wave, a.regex, _t(a, a.t0) or 0, _t(a, a.t1))
    if a.json:
        jsonout.write(r)
    else:
        for s in r['signals']:
            extra = f" rising {s['rising']} falling {s['falling']}" if 'rising' in s else ''
            print(f"{s['signal']}: changes {s['changes']}{extra} unknown {s['unknown']}")
    return 0


@_wrap
def _value(a):
    from .typed import value
    from .vcd import end_time
    from ..query.db import default_db
    database = a.db or default_db()
    if not database:
        raise WaveError("no design database: pass --db or set RVW_DESIGNDB")
    t = end_time(a.wave) if a.at == "end" else _t(a, a.at)
    r = value(database, a.wave, a.name, t, "dec" if a.dec else "hex")
    if a.json:
        jsonout.write(r)
    else:
        print(f"# {r['name']} ({r['type']}) @ {t}" + (f"  fire={r['fire']}" if 'fire' in r else ""))

        def show(node, pad):
            if 'value' in node and 'wave' in node:
                print(f"{pad}= {node['value']}" + (f" ({node['enum']})" if 'enum' in node else ""))
                return
            for k, v in node.items():
                if 'wave' in v:
                    print(f"{pad}{k} = {v['value']}" + (f" ({v['enum']})" if 'enum' in v else ""))
                else:
                    print(f"{pad}{k}:")
                    show(v, pad + "  ")
        show(r['value'], "  ")
        if r['missing_in_wave']:
            print(f"# not in the wave: {', '.join(r['missing_in_wave'][:8])}")
    return 0


@_wrap
def _seq(a):
    from .temporal import sequence
    from .typed import enums
    r = sequence(a.wave, a.sequence, _t(a, a.t0) or 0, _t(a, a.t1), a.clock, a.limit, enums(a.db) if a.db else None)
    if a.json:
        jsonout.write(r)
    else:
        print(f"# clock {r['clock']}, {r['cycles']} edges: {r['matched']} matched, {r['failed']} failed, "
              f"{r['pending']} pending at window end")
        for m in r['matches']:
            print(f"match {m['start']} .. {m['end']} ({m['cycles']} cycles)")
        for f in r['failures']:
            print(f"fail  {f['start']}: step {f['failed_step']} ({f['expr']}) not seen by {f['at']}")
    return 0


@_wrap
def _txn(a):
    from .temporal import stream_signals, transactions
    names = None
    if a.stream:
        from ..query.db import default_db
        database = a.db or default_db()
        if not database:
            raise WaveError("--stream needs a design database: pass --db or set RVW_DESIGNDB")
        s = stream_signals(database, a.stream)
        valid, ready, names = s['valid'], s['ready'], s['payload']
    elif a.valid:
        valid, ready = a.valid, a.ready
    else:
        raise WaveError("pass --valid [--ready] [--payload] or --stream with a database")
    r = transactions(a.wave, valid, ready, a.payload, _t(a, a.t0) or 0, _t(a, a.t1), a.clock, a.limit,
                     payload_names=names)
    if a.json:
        jsonout.write(r)
    else:
        print(f"# {r['kind']} {r['valid']}: {r['transfers']} transfers in {r['edges']} edges, "
              f"{r['stall_edges']} stalled, {r['unknown_edges']} unknown, max wait {r['max_wait_cycles']}")
        for x in r['transactions']:
            pay = " ".join(f"{k.rsplit('.', 1)[-1]}={v}" for k, v in x['payload'].items())
            print(f"{x['time']:10d} wait {x['wait_cycles']} {pay}")
        for i in r['issues']:
            print(f"ISSUE {i['time']}: {i['issue']} (waiting since {i['since']})")
    return 0


@_wrap
def _diff(a):
    from .wdiff import diff
    mapping = None
    if a.map:
        if "=" not in a.map:
            raise WaveError("--map takes A_PREFIX=B_PREFIX")
        mapping = tuple(a.map.split("=", 1))
    if a.align:
        from .wdiff import aligned_diff
        r = aligned_diff(a.wave, a.other, a.align, a.signals, a.clock, mapping, a.align_b,
                         _t(a, a.t0) or 0, _t(a, a.t1), a.limit, not a.all)
    else:
        r = diff(a.wave, a.other, a.signals, _t(a, a.t0) or 0, _t(a, a.t1), a.offset,
                 a.clock if a.on_clock else None, mapping, a.limit, not a.all)
    if a.json:
        jsonout.write(r)
    else:
        points = r.get('points_compared', r.get('events_compared'))
        print(f"# {r['status']}: {r['signals_compared']} signals, {points} points ({r['mode']})")
        first = r['first_divergence']
        if isinstance(first, dict):
            print(f"first divergence at event {first['event']}"
                  + (f" (A {first['a_time']}, B {first['b_time']})" if 'a_time' in first else f": {first['cause']}"))
            for d in first.get('signals', []):
                print(f"  {d['signal']}: A={d['a']} B={d['b']}")
        elif first is not None:
            print(f"first divergence at {first}:")
            for d in r['divergent']:
                print(f"  {d['signal']}: A={d['a']} B={d['b']}")
        if r.get('only_in_a_count'):
            print(f"# {r['only_in_a_count']} signals only in A")
    return 0 if r['status'] == 'match' else 1


def _bench(a):
    from .tasks import run
    try:
        variables = dict(v.split("=", 1) for v in a.var if "=" in v)
        r = run(a.tasks, variables, a.task, a.timeout)
        if a.json:
            jsonout.write(r)
        else:
            for t in r['results']:
                print(f"{t['id']}: {t['status']}" + (f" in {t['seconds']} s" if 'seconds' in t else "")
                      + (f" ({t['cause']})" if t.get('cause') else ""))
            print(f"# {r['solved']}/{r['total']} solved; {r['comparison']}")
        return 0 if r['solved'] == r['total'] else 1
    except (WaveError, jsonout.JsonOutputError) as e:
        if a.json:
            jsonout.write({'error': str(e)})
        print(f"rvw wave: {e}", file=sys.stderr)
        return 2


def _session_save(a):
    from .session import save
    try:
        r = save(a.out, a.wave, a.db, a.signal, a.cursor, a.query, a.artifact, a.note)
        if a.json:
            jsonout.write(r)
        else:
            print(f"wrote {a.out}: {len(r['artifacts'])} artifacts, {len(r['signals'])} signals")
        return 0
    except (WaveError, CaptureError, jsonout.JsonOutputError) as e:
        if a.json:
            jsonout.write({'error': str(e)})
        print(f"rvw wave: {e}", file=sys.stderr)
        return 2


def _session_open(a):
    from .session import open_session
    try:
        r = open_session(a.session, a.root)
        if a.json:
            jsonout.write(r)
        else:
            print(f"# session {r['status']}")
            for k, v in r['artifacts'].items():
                print(f"{k}: {v['status']} {v.get('path') or v.get('recorded')}")
            if r['missing_signals']:
                print(f"missing signals: {', '.join(r['missing_signals'])}")
        return 0 if r['status'] == 'complete' else 1
    except (WaveError, CaptureError, jsonout.JsonOutputError) as e:
        if a.json:
            jsonout.write({'error': str(e)})
        print(f"rvw wave: {e}", file=sys.stderr)
        return 2


def _why(a):
    from .why import why
    from ..query.db import QueryError, default_db
    try:
        database = a.db or default_db()
        if not database:
            raise WaveError("no design database: pass --db or set RVW_DESIGNDB")
        r = why(database, a.wave, a.signal, _t(a, a.at), a.depth, a.max_nodes)
        if a.json:
            jsonout.write(r)
        else:
            _print_why(r['trace'], 0)
            if r['truncated']:
                print(f"(stopped after {r['nodes']} signals; raise --max-nodes)")
            print(f"# {r['binding']}")
        return 0
    except (WaveError, QueryError, CaptureError, jsonout.JsonOutputError) as e:
        if a.json:
            jsonout.write({'error': str(e)})
        print(f"rvw wave: {e}", file=sys.stderr)
        return 2


def _print_why(n, level):
    pad = "  " * level
    head = f"{pad}{n['signal']} = {n['value']} @ {n['time']}"
    if n.get('set_at') is not None:
        head += f" (set at {n['set_at']})"
    print(f"{head}  [{n.get('status')}]" + (f" {n['cause']}" if n.get('cause') else ""))
    for c in n.get('assignments', []):
        if c['id'] == n.get('active'):
            cond = " && ".join(f"{x['kind']}({x['expr']})={x['holds']}" for x in c['conditions'])
            print(f"{pad}  := {c['source']}" + (f"  under {cond}" if cond else "") + (f"  at {c['loc']}" if c['loc'] else ""))
    for r in n.get('reads', []):
        if r['kind'] != 'data':
            print(f"{pad}  reads {r['signal']} ({r['kind']}) = {r['value']}")
    for child in n.get('children', []):
        _print_why(child, level + 1)


def _verify(a):
    from .index import verify
    try:
        r = verify(a.index, a.source)
        if a.json:
            jsonout.write(r)
        else:
            print(f"{a.index}: {'fresh' if r['fresh'] else 'STALE: ' + r['reason']}")
        return 0 if r['fresh'] else 1
    except (WaveError, jsonout.JsonOutputError) as e:
        if a.json:
            jsonout.write({'error': str(e)})
        print(f"rvw wave: {e}", file=sys.stderr)
        return 2


def _index(a):
    from .index import build
    try:
        result = build(a.wave, a.out, a.reader)
        if a.json:
            jsonout.write(result)
        else:
            print(f"wrote {a.out}: {result['records']} records")
        return 0
    except (WaveError, CaptureError, jsonout.JsonOutputError) as e:
        print(f"rvw wave: {e}", file=sys.stderr)
        return 2
