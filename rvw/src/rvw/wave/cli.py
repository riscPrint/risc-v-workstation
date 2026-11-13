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
    q.set_defaults(func=_changes)

    q = w.add_parser("sample", help="value of matching signals at one time")
    common(q)
    q.add_argument("--at", required=True, help=TIME_HELP + "; 'end' for the last timestamp")
    q.add_argument("--dec", action="store_true", help="decimal instead of hex")
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
    q.set_defaults(func=_find)

    q = w.add_parser("edges", help="value changes, rising and falling edges per signal in a window")
    common(q)
    q.add_argument("--from", dest="t0", help=TIME_HELP)
    q.add_argument("--to", dest="t1", help=TIME_HELP)
    q.set_defaults(func=_edges)

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
    if a.json:
        jsonout.write(page)
    else:
        for r in page["changes"]:
            print(f"{r['time']:10d} {r['signal']} = {r['value']}")
    if page["truncated"]:
        print(f"rvw wave: truncated at {page['limit']} changes; narrow --from/--to or the regex, "
              "or raise --limit (0 = no limit)", file=sys.stderr)
    return 0


@_wrap
def _sample(a):
    from .vcd import end_time
    t = end_time(a.wave) if a.at == "end" else _t(a, a.at)
    vals = ops.sample(a.wave, a.regex, t, "dec" if a.dec else "hex")
    if a.json:
        jsonout.write({"time": t, "values": vals}, indent=1)
    else:
        print(f"# t={t}")
        for k, v in vals.items():
            print(f"{k} = {v if v is not None else '?'}")
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
    r = find(a.wave, a.expr, _t(a, a.t0) or 0, _t(a, a.t1), a.limit)
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
