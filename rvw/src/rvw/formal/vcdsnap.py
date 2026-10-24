"""Cut one simulation state out of a waveform, in a form Yosys `sim -r <vcd> -at <T> -w` can load.

VCD parsing stops right after the requested state. FST conversion first writes a temporary VCD and
checks the converter exit status, so a truncated conversion cannot supply replay evidence.
The snapshot keeps the variables under one scope (the design's toplevel instance) and
rewrites Verilator's memory dumps: Verilator puts the words of memory `m` in a sub-scope (`m.m[3]`),
Yosys expects them next to the other signals (`m[3]`).
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Iterator

from rvw.common.proc import run_group

from .common import die, need
from .tools import ACTIVE


@dataclass
class Var:
    kind: str
    width: int
    code: str
    path: list[str]  # scope names + reference
    rng: str = ""    # trailing range text, e.g. "[7:0]"


@dataclass
class Snapshot:
    time: int
    timescale: str
    cycle: int | None
    clock_edges: int
    vars: list[Var] = field(default_factory=list)
    values: dict = field(default_factory=dict)
    memories: list[str] = field(default_factory=list)  # hoisted memory scopes


def open_trace(path: Path, timeout: float | None = None) -> IO[str]:
    """A VCD stream. Decode FST completely so a failed converter cannot supply partial evidence."""
    if str(path).endswith(".fst"):
        stream = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="strict")
        try:
            active = ACTIVE.get()
            result = run_group([need("fst2vcd"), "-f", str(path)], stdout=stream,
                               env=active.env if active is not None else None,
                               stderr=subprocess.PIPE, timeout=timeout)
            if result.timed_out or result.returncode != 0:
                die(f"FST conversion failed (exit {result.returncode}): {result.stderr or ''}")
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise
    return open(path, encoding="utf-8", errors="strict")


def _tokens(stream: IO[str]) -> Iterator[str]:
    for line in stream:
        yield from line.split()


def _word(it: Iterator[str]) -> str:
    try:
        return next(it)
    except StopIteration:
        die("truncated VCD command or value change")


def _command(it: Iterator[str]) -> list[str]:
    parts = []
    while (tok := _word(it)) != "$end":
        parts.append(tok)
    return parts


# Real/event/string values cannot describe persistent binary state for replay.
_KINDS = {"wire", "reg", "logic", "bit", "integer", "time", "parameter", "supply0", "supply1",
          "tri", "triand", "trior", "trireg", "tri0", "tri1", "wand", "wor"}


def _header(it: Iterator[str]) -> tuple[list[Var], str, list[str]]:
    stack: list[str] = []
    variables: list[Var] = []
    scope_paths: list[str] = []
    paths: set[tuple[str, ...]] = set()
    widths: dict[str, int] = {}
    timescale = None
    for tok in it:
        if tok in ("$comment", "$date", "$version"):
            _command(it)
        elif tok == "$timescale":
            value = "".join(_command(it))
            if timescale is not None or not re.fullmatch(r"1(s|ms|us|ns|ps|fs)", value):
                die(f"unsupported or repeated VCD timescale {value!r}; needs 1<unit>")
            timescale = value
        elif tok == "$scope":
            parts = _command(it)
            if len(parts) != 2 or parts[0] not in {"module", "task", "function", "begin", "fork"}:
                die("unsupported VCD scope declaration")
            stack.append(parts[1])
            scope_paths.append(".".join(stack))
        elif tok == "$upscope":
            if _command(it) or not stack:
                die("unbalanced VCD scope")
            stack.pop()
        elif tok == "$var":
            parts = _command(it)
            if len(parts) < 4:
                die("malformed VCD variable declaration")
            kind, width_text, code, ref, *tail = parts
            if kind not in _KINDS or not re.fullmatch(r"[0-9]+", width_text) or int(width_text) < 1:
                die(f"unsupported VCD variable type or width: {parts!r}")
            width = int(width_text)
            rng = "".join(tail)
            if rng and not re.fullmatch(r"\[-?\d+(?::-?\d+)?\]", rng):
                die(f"unsupported VCD variable range {rng!r}")
            if rng and ":" in rng:
                high, low = map(int, rng[1:-1].split(":"))
                if abs(high - low) + 1 != width:
                    die(f"VCD range {rng!r} disagrees with width {width}")
            if not stack or tuple(stack + [ref]) in paths:
                die(f"duplicate or unscoped VCD variable {ref!r}")
            if code in widths and widths[code] != width:
                die(f"VCD aliases of {code!r} have different widths")
            if any(not 33 <= ord(c) <= 126 for c in code):
                die("invalid VCD identifier code")
            paths.add(tuple(stack + [ref]))
            widths[code] = width
            variables.append(Var(kind, width, code, stack.copy() + [ref], rng))
        elif tok == "$enddefinitions":
            if _command(it) or stack or timescale is None:
                die("incomplete VCD header (scopes or timescale)")
            return variables, timescale, scope_paths
        else:
            die(f"unsupported VCD header token {tok!r}")
    die("VCD header has no $enddefinitions")


def scopes(stream: IO[str]) -> list[str]:
    """Scope paths in a validated VCD header, for picking `--scope`."""
    return _header(_tokens(stream))[2]


def take(path: Path, scope: str, clock: str | None, cycle: int | None, time: int | None,
         timeout: float | None = None) -> Snapshot:
    """Decode a trace and take the requested simulation state."""
    with open_trace(path, timeout) as stream:
        return take_stream(stream, scope, clock, cycle, time)


def take_stream(stream: IO[str], scope: str, clock: str | None, cycle: int | None,
                time: int | None) -> Snapshot:
    """The values at `time`, or right after the `cycle`-th rising edge (1-based) of `scope.clock`."""
    if (cycle is None) == (time is None):
        raise ValueError("give exactly one of cycle or time")
    if cycle is not None and cycle < 1:
        die("--cycle must be >= 1")
    return _take(stream, scope.split("."), clock, cycle, time)


def _take(stream: IO[str], want: list[str], clock: str | None, cycle: int | None, time: int | None) -> Snapshot:
    # One token stream covers the header and body. Newlines have no VCD meaning.
    it = _tokens(stream)
    all_vars, timescale, _ = _header(it)
    widths = {v.code: v.width for v in all_vars}
    vars_ = [Var(v.kind, v.width, v.code, v.path[len(want):], v.rng)
             for v in all_vars if v.path[:len(want)] == want]
    if not vars_:
        die(f"no variables under VCD scope {'.'.join(want)}")

    # Hoist memory scopes: a scope `m` whose variables are all `m[<n>]`.
    by_scope: dict[tuple, list[Var]] = {}
    for v in vars_:
        by_scope.setdefault(tuple(v.path[:-1]), []).append(v)
    memories = []
    for sc, vs in by_scope.items():
        if sc and all(re.fullmatch(re.escape(sc[-1]) + r"\[\d+\]", v.path[-1]) for v in vs):
            memories.append(".".join(sc))
            for v in vs:
                v.path = list(sc[:-1]) + [v.path[-1]]

    if len({tuple(v.path) for v in vars_}) != len(vars_):
        die("VCD memory hoisting creates duplicate variable paths")

    codes = {v.code for v in vars_}
    clock_code = None
    if cycle is not None:
        for v in vars_:
            if v.path == [clock]:
                clock_code = v.code
        if clock_code is None:
            die(f"clock '{clock}' not found under scope {'.'.join(want)}")
        codes.add(clock_code)

    if clock_code is not None and widths[clock_code] != 1:
        die("VCD clock must have width 1")

    # ---- values ----
    values: dict[str, str] = {}
    now = 0
    first: int | None = None
    edges = 0
    target = time
    clock_val = "x"
    last_rising_time: int | None = None
    passed = False
    dump = None
    for tok in it:
        c = tok[0]
        if tok == "$comment":
            _command(it)
            continue
        if tok in ("$dumpvars", "$dumpall", "$dumpon"):
            if dump is not None:
                die("nested VCD dump command")
            dump = tok
            continue
        if tok == "$end":
            if dump is None:
                die("unexpected VCD $end")
            dump = None
            continue
        if c == "#":
            if dump is not None or not re.fullmatch(r"[0-9]+", tok[1:]):
                die(f"malformed VCD timestamp {tok!r}")
            t = int(tok[1:])
            if first is not None and t < now:
                die("VCD timestamps go backwards")
            if first is None:
                first = t
                if time is not None and time < t:
                    die(f"--time {time} is before the first recorded time of the trace ({t})")
            if target is not None and t > target:
                passed = True
                break
            now = t
            continue
        if c in "bB":
            val, code = tok[1:].lower(), _word(it)
            if not val or not re.fullmatch("[01xz]+", val):
                die(f"malformed VCD binary value {tok!r}")
            value = "b" + val
        elif c in "01xXzZ":
            val, code = c.lower(), tok[1:]
            value = val
        else:
            # In particular, $dumpoff loses state changes; retaining old values is unsound.
            die(f"unsupported VCD value or command {tok!r}")
        if code not in widths:
            die(f"VCD value uses undeclared identifier {code!r}")
        width = widths[code]
        if (value[0] == "b" and len(val) > width) or (value[0] != "b" and width != 1):
            die(f"VCD value {tok!r} does not fit identifier {code!r}")
        if code in codes:
            values[code] = value
            if code == clock_code:
                if val in {"x", "z"}:
                    die("cannot count cycles through an unknown VCD clock value")
                if clock_val == "0" and val == "1":
                    if last_rising_time == now:
                        die("cannot select a cycle with multiple rising clock edges at one VCD time")
                    last_rising_time = now
                    edges += 1
                    if edges == cycle:
                        target = now
                clock_val = val
    if dump is not None:
        die("unterminated VCD dump command")
    if target is None:
        die(f"the trace ends after {edges} rising edges of {clock}, before cycle {cycle}")
    if time is not None and not passed and (first is None or time > now):
        # Past the last timestamp nothing is recorded: the values there are not the state at `time`.
        rec = "no timestamps" if first is None else f"times {first}..{now}"
        die(f"--time {time} is outside the trace (it records {rec})")
    return Snapshot(time=target, timescale=timescale, cycle=cycle, clock_edges=edges, vars=vars_,
                    values=values, memories=memories)


def write(snap: Snapshot, out: Path, top_scope: str) -> None:
    """A one-timestamp VCD (`#<time>` holding every value) rooted at `top_scope`."""
    lines = [f"$timescale {snap.timescale} $end"]
    tree: dict = {}
    for v in snap.vars:
        node = tree
        for s in v.path[:-1]:
            node = node.setdefault(("scope", s), {})
        node.setdefault(("vars",), []).append(v)

    def emit(node: dict) -> None:
        for v in node.get(("vars",), []):
            rng = f" {v.rng}" if v.rng else ""
            lines.append(f"$var {v.kind} {v.width} {v.code} {v.path[-1]}{rng} $end")
        for k, child in node.items():
            if k[0] == "scope":
                lines.append(f"$scope module {k[1]} $end")
                emit(child)
                lines.append("$upscope $end")

    for s in top_scope.split("."):
        lines.append(f"$scope module {s} $end")
    emit(tree)
    for _ in top_scope.split("."):
        lines.append("$upscope $end")
    lines.append("$enddefinitions $end")
    lines.append(f"#{snap.time}")
    lines.append("$dumpvars")
    written = set()
    for v in snap.vars:
        if v.code in written:
            continue
        written.add(v.code)
        val = snap.values.get(v.code)
        if val is None:
            continue
        if val[0] == "b":
            lines.append(f"{val} {v.code}")
        else:
            lines.append(f"{val}{v.code}" if v.width == 1 else f"b{val} {v.code}")
    lines.append("$end")
    out.write_text("\n".join(lines) + "\n")
