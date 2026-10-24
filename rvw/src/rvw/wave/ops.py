"""Wave queries used by `rvw wave` and by other tools (bundle, reduce).

Public operations capture the raw input once. Parsers stream the copy and stop
when they have the data they need.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass

from ..common.proc import run_group
from . import vcd
from .capture import captured, _current
from .vcd import Var, WaveError

CLOCK_RX = r"(^|\.)(clk|clock|clk_i|clock_i)$"


def _validate_bounds(t0: int, t1: int | None) -> None:
    if t0 < 0 or (t1 is not None and t1 < 0):
        raise WaveError('wave time bounds must be non-negative')
    if t1 is not None and t1 < t0:
        raise WaveError('wave end time must not be before start time')


@dataclass
class Info:
    path: str
    timescale: str
    signals: int
    start: int | None
    end: int | None
    period: int | None


@captured
def list_signals(path: str, regex: str | None = None) -> list[Var]:
    with vcd.open_text(path) as f:
        return vcd.read_header(f).match(regex)


@captured
def changes(path: str, regex: str, t0: int = 0, t1: int | None = None,
            limit: int | None = None, radix: str = "hex") -> list[dict]:
    """Value changes of the signals matching `regex` in [t0, t1]."""
    _validate_bounds(t0, t1)
    if limit is not None and limit < 0:
        raise WaveError('wave change limit must be non-negative')
    out: list[dict] = []
    with vcd.open_text(path) as f:
        hdr = vcd.read_header(f)
        vars = hdr.match(regex)
        by_code: dict[str, list[Var]] = {}
        for v in vars:
            by_code.setdefault(v.code, []).append(v)
        if not by_code:
            return out
        for t, code, raw in vcd.body_changes(f, set(by_code), t0, t1):
            for v in by_code[code]:
                out.append({"time": t, "signal": v.name, "value": vcd.fmt_value(raw, v.width, radix)})
            if limit is not None and len(out) >= limit:
                return out[:limit]
    return out


DEFAULT_CHANGES_LIMIT = 10000


@captured
def changes_page(path: str, regex: str, t0: int = 0, t1: int | None = None,
                 limit: int | None = DEFAULT_CHANGES_LIMIT, radix: str = "hex") -> dict:
    """`changes` with an explicit bound: {"changes": [...], "truncated": bool, "limit": N}.
    `truncated` is true when more changes match than `limit` (None or 0: no limit)."""
    if limit is not None and limit < 0:
        raise WaveError('wave change limit must be non-negative')
    lim = limit or None
    rows = changes(path, regex, t0, t1, lim + 1 if lim else None, radix)
    truncated = bool(lim) and len(rows) > lim
    return {"changes": rows[:lim] if lim else rows, "truncated": truncated, "limit": lim}


@captured
def sample(path: str, regex: str | None, t: int, radix: str = "hex",
           vars: list[Var] | None = None) -> dict[str, str | None]:
    """Value of each matching signal at time `t` (after all changes at `t`). None if never set."""
    _validate_bounds(t, None)
    with vcd.open_text(path) as f:
        hdr = vcd.read_header(f)
        if vars is None:
            vars = hdr.match(regex)
        codes = {v.code for v in vars}
        vals, _ = vcd.state_at(f, t, codes)
    return {v.name: (vcd.fmt_value(vals[v.code], v.width, radix) if v.code in vals else None)
            for v in vars}


@captured
def sample_raw(path: str, names: list[str], t: int) -> dict[str, str | None]:
    """Raw values of exact signal names at time `t` (for callers that decode values themselves)."""
    _validate_bounds(t, None)
    with vcd.open_text(path) as f:
        hdr = vcd.read_header(f)
        want = set(names)
        vars = [v for v in hdr.vars if v.name in want]
        vals, _ = vcd.state_at(f, t, {v.code for v in vars})
    return {v.name: vals.get(v.code) for v in vars}


@captured
def detect_period(path: str, clock: str = CLOCK_RX, max_lines: int = 2_000_000) -> int | None:
    """Clock period from the first two rising edges of the clock signal (None if not found)."""
    with vcd.open_text(path) as f:
        hdr = vcd.read_header(f)
        clk = [v for v in hdr.match(clock) if v.width == 1]
        if not clk:
            return None
        # Prefer the shallowest clock (the top-level one)
        clk.sort(key=lambda v: v.name.count("."))
        code = clk[0].code
        rises: list[int] = []
        prev = None
        for n, (now, cd, raw) in enumerate(vcd.body_records(f)):
            if n >= max_lines:
                break
            if cd == code:
                value = vcd.to_int(raw)
                if value == 1 and prev == 0:
                    rises.append(now)
                    if len(rises) == 3:
                        return rises[2] - rises[1]
                prev = value
        return rises[1] - rises[0] if len(rises) >= 2 else None


@captured
def info(path: str, clock: str = CLOCK_RX) -> Info:
    with vcd.open_text(path) as f:
        hdr = vcd.read_header(f)
        start = None
        for t, code, _ in vcd.body_records(f):
            if code is None:
                start = t
                break
    return Info(path, hdr.timescale, len(hdr.vars), start, vcd.end_time(path),
                detect_period(path, clock))


@captured
def cut(path: str, out: str, t0: int, t1: int | None = None, regex: str | None = None,
        rebase: bool = False) -> dict:
    """Write the window [t0, t1] of `path` to `out` (.vcd, .vcd.gz or .fst).

    The output starts with a $dumpvars block holding every kept signal's value at `t0`, so it is a
    complete waveform on its own. `regex` keeps only the matching signals. `rebase` shifts times so
    the window starts at 0.
    """
    _validate_bounds(t0, t1)
    if os.path.exists(out) and os.path.samefile(path, out):
        raise WaveError(f"{out} is the input wave; cut to a different file")
    fst_out = out.endswith(".fst")
    tmp = None
    if fst_out:
        if not vcd.tool("vcd2fst"):
            raise WaveError("writing FST needs vcd2fst (GTKWave / oss-cad-suite) on PATH")
        fd, tmp = tempfile.mkstemp(suffix=".vcd", dir=os.path.dirname(os.path.abspath(out)) or ".")
        os.close(fd)
        vcd_out = tmp
    else:
        vcd_out = out
    shift = t0 if rebase else 0
    n_changes = 0
    last_t = t0
    with vcd.open_text(path) as f:
        hdr = vcd.read_header(f)
        kept = hdr.match(regex)
        codes = {v.code for v in kept} if regex is not None else None
        opener = (lambda p: __import__("gzip").open(p, "wt")) if vcd_out.endswith(".gz") \
            else (lambda p: open(p, "w", buffering=1 << 20))
        with opener(vcd_out) as o:
            _write_header(o, hdr, kept)
            vals: dict[str, str] = {}
            now = 0
            phase = 0      # 0 before window, 1 inside
            for now, code, raw in vcd.body_records(f):
                if phase == 0 and now > t0:
                    _dump_state(o, vals, t0 - shift)
                    phase = 1
                if t1 is not None and now > t1:
                    break
                if phase == 0:
                    if code is not None and (codes is None or code in codes):
                        vals[code] = raw
                elif code is None:
                    o.write(f"#{now - shift}\n")
                    last_t = now
                elif codes is None or code in codes:
                    vcd.write_value(o, raw, code)
                    n_changes += 1
            if phase == 0:
                # The file ended inside or before the window: dump what we have
                _dump_state(o, vals, t0 - shift)
            if t1 is not None and last_t < t1:
                o.write(f"#{t1 - shift}\n")
    if fst_out:
        try:
            result = run_group([vcd.tool("vcd2fst"), vcd_out, out], capture=True,
                               env=_current.get().environment if _current.get() else None)
            if result.returncode:
                raise WaveError(f"vcd2fst failed: {result.stderr or result.returncode}")
        finally:
            os.unlink(vcd_out)
    return {"out": out, "from": t0, "to": t1, "signals": len(kept), "changes": n_changes,
            "bytes": os.path.getsize(out)}


def _dump_state(o, vals: dict[str, str], t: int) -> None:
    o.write(f"#{t}\n$dumpvars\n")
    for code, raw in vals.items():
        vcd.write_value(o, raw, code)
    o.write("$end\n")


def _write_header(o, hdr: vcd.Header, vars: list[Var]) -> None:
    """Header with only `vars`, scopes rebuilt from their dotted names."""
    o.write(f"$timescale {hdr.timescale} $end\n")
    cur: list[str] = []
    seen: set[tuple[str, str]] = set()
    for v in sorted(vars, key=lambda v: v.name.split(".")[:-1]):
        parts = v.name.split(".")
        scope, leaf = parts[:-1], parts[-1]
        k = 0
        while k < len(cur) and k < len(scope) and cur[k] == scope[k]:
            k += 1
        for _ in range(len(cur) - k):
            o.write("$upscope $end\n")
        for s in scope[k:]:
            o.write(f"$scope module {s} $end\n")
        cur = scope
        key = (v.code, v.name)
        if key in seen:
            continue
        seen.add(key)
        rng = f" {v.range}" if v.range else ""
        o.write(f"$var {v.kind} {v.width} {v.code} {leaf}{rng} $end\n")
    for _ in cur:
        o.write("$upscope $end\n")
    o.write("$enddefinitions $end\n")


def parse_time(s: str | None, period: int | None) -> int | None:
    """'1234' is a time; '1234c' is cycle 1234 (needs the clock period)."""
    if s is None:
        return None
    s = s.strip()
    m = re.fullmatch(r"(\d+)\s*c(ycles?)?", s)
    if m:
        if not period:
            raise WaveError(f"'{s}' is in cycles but the clock period is unknown: pass --period")
        return int(m.group(1)) * period
    try:
        return int(s)
    except ValueError as exc:
        raise WaveError(f'invalid wave time: {s!r}; use an integer or Nc for cycle N') from exc
