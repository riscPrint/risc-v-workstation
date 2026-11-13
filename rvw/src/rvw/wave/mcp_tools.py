"""Waveform MCP tools sharing the CLI's operations and time conversion (C7)."""
from rvw.mcp.spec import ToolSpec, schema

from . import ops
from .capture import captured
from .cli import time_at
from .vcd import end_time

S = {"type": "string"}
B = {"type": "boolean", "default": False}
WAVE = {"wave": {**S, "description": "input .vcd, .vcd.gz, .fst or .rvwi index path"},
        "indexed": {**B, "description": "use a cached index, built on first use and rebuilt when the wave changes"}}
REGEX = {"regex": {**S, "description": "Python regex over dotted signal paths"}}
TIME = {"period": {"type": "integer", "minimum": 1, "description": "clock period in wave units; otherwise detected"},
        "clock": {**S, "default": ops.CLOCK_RX, "description": "clock regex for period detection"}}
WINDOW = {"t0": {**S, "description": "start time in wave units or Nc for cycle N"},
          "t1": {**S, "description": "inclusive end time in wave units or Nc; default end"}}
RO = {"readOnlyHint": True}


@captured
def _info(wave, clock=ops.CLOCK_RX):
    return vars(ops.info(wave, clock))


@captured
def _list(wave, regex=None):
    return [{"name": v.name, "width": v.width, "kind": v.kind, "code": v.code}
            for v in ops.list_signals(wave, regex)]


@captured
def _changes(wave, regex, t0=None, t1=None, limit=ops.DEFAULT_CHANGES_LIMIT, dec=False, period=None,
             clock=ops.CLOCK_RX):
    return ops.changes_page(wave, regex, time_at(wave, t0, period, clock) or 0,
                            time_at(wave, t1, period, clock), limit, "dec" if dec else "hex")


@captured
def _sample(wave, regex, at, dec=False, period=None, clock=ops.CLOCK_RX):
    t = end_time(wave) if at == "end" else time_at(wave, at, period, clock)
    return {"time": t, "values": ops.sample(wave, regex, t, "dec" if dec else "hex")}


@captured
def _cut(wave, out, t0, t1=None, signals=None, rebase=False, period=None, clock=ops.CLOCK_RX):
    return ops.cut(wave, out, time_at(wave, t0, period, clock), time_at(wave, t1, period, clock),
                   signals, rebase)


def _indexed(fn):
    """Swap the wave for its cached index when `indexed` is true."""
    import functools

    @functools.wraps(fn)
    def call(wave, *args, indexed=False, **kwargs):
        if indexed:
            from .index import ensure
            wave = ensure(wave)
        return fn(wave, *args, **kwargs)
    return call


def _find(wave, expr, t0=None, t1=None, limit=1000, period=None, clock=ops.CLOCK_RX):
    from .search import find
    return find(wave, expr, time_at(wave, t0, period, clock) or 0, time_at(wave, t1, period, clock), limit)


def _edges(wave, regex, t0=None, t1=None, period=None, clock=ops.CLOCK_RX):
    from .search import edges
    return edges(wave, regex, time_at(wave, t0, period, clock) or 0, time_at(wave, t1, period, clock))


def _index(wave, out, reader="auto"):
    from .index import build
    return build(wave, out, reader)


def _verify(index, source=None):
    from .index import verify
    return verify(index, source)


def mcp_tools():
    return [
        ToolSpec("wave_info", "Inspect timescale, signal count, time range and clock period of a waveform.",
                 schema({**WAVE, "clock": TIME["clock"]}, ["wave"]), _indexed(_info), annotations=RO),
        ToolSpec("wave_list", "List waveform signal paths, widths, kinds and codes, optionally matching a regex.",
                 schema({**WAVE, **REGEX}, ["wave"]), _indexed(_list), annotations=RO),
        ToolSpec("wave_changes", "Read changes of matching signals within a time window. Returns {changes, "
                 "truncated, limit}; limit defaults to 10000 (0 = no limit) and truncated says more matched.",
                 schema({**WAVE, **REGEX, **TIME, **WINDOW,
                         "limit": {"type": "integer", "minimum": 0, "default": ops.DEFAULT_CHANGES_LIMIT},
                         "dec": B}, ["wave", "regex"]), _indexed(_changes), annotations=RO),
        ToolSpec("wave_sample", "Read matching signal values at a wave time, cycle Nc, or end.",
                 schema({**WAVE, **REGEX, **TIME, "at": S, "dec": B}, ["wave", "regex", "at"]),
                 _indexed(_sample), annotations=RO),
        ToolSpec("wave_find", "Find when an expression over several signals holds: first time, last interval and "
                 "all intervals in a window. Syntax: && || ! == < + & bit selects sig[7:0], rose(s), fell(s), "
                 "changed(s), stable(s), known(s); x/z make the result unknown, which never counts as true.",
                 schema({**WAVE, **TIME, **WINDOW, "expr": S,
                         "limit": {"type": "integer", "minimum": 0, "default": 1000}}, ["wave", "expr"]),
                 _indexed(_find), annotations=RO),
        ToolSpec("wave_edges", "Count value changes, rising and falling edges and x/z transitions per matching signal.",
                 schema({**WAVE, **REGEX, **TIME, **WINDOW}, ["wave", "regex"]), _indexed(_edges), annotations=RO),
        ToolSpec("wave_index", "Build an identity-bound .rvwi index of a VCD/FST wave for fast window, sample and search queries.",
                 schema({"wave": WAVE["wave"], "out": S,
                         "reader": {"enum": ["auto", "vcd", "wellen"], "default": "auto"}}, ["wave", "out"]), _index),
        ToolSpec("wave_index_verify", "Check a .rvwi index against its source wave by full SHA-256 (fresh true/false).",
                 schema({"index": S, "source": S}, ["index"]), _verify, annotations=RO),
        ToolSpec("wave_cut", "Write a self-contained waveform window, optionally keeping selected signals and rebasing time.",
                 schema({**WAVE, **TIME, **WINDOW, "out": S, "signals": S, "rebase": B},
                        ["wave", "out", "t0"]), _indexed(_cut)),
    ]
