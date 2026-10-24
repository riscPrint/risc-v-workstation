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
    p = sub.add_parser("wave", help="query and cut VCD/FST waveforms (streaming)",
                       description=__doc__)
    w = p.add_subparsers(dest="wave_cmd", required=True)

    def common(q, regex=True, regex_required=True):
        q.add_argument("wave", help=".vcd, .vcd.gz or .fst")
        if regex:
            q.add_argument("regex", nargs=None if regex_required else "?",
                           help="Python regex searched in dotted signal paths (TOP.Top.unit.sig)")
        q.add_argument("--json", action="store_true", help="JSON output")
        q.add_argument("--period", type=int, help="clock period in wave time units (for 'Nc')")
        q.add_argument("--clock", default=ops.CLOCK_RX, help="clock signal regex for period detection")

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
    q.add_argument("-o", "--out", required=True, help="output .vcd, .vcd.gz or .fst")
    q.set_defaults(func=_cut)

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
