"""Streaming VCD reader.

The reader never holds the value changes in memory: the header is parsed once, then the body is
read as whitespace-separated records. FST files are converted with `fst2vcd` (GTKWave,
shipped with oss-cad-suite) into a temporary disk file before queries stream that file.

Names are the dotted scope path of each variable, including the top scope that Verilator calls
`TOP` (`TOP.BoomSimTop.core.rob.rob_head_idx`). A separate bit-range token (`[7:0]`) is kept in `Var.range`. Brackets within the
reference token belong to the name, including unpacked array indexes.
"""
from __future__ import annotations

import contextlib
import gzip
import io
import os
import re
import shutil
import subprocess
import tempfile

from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator, TextIO

from ..common.proc import run_group
from .capture import _current, captured


@dataclass
class Var:
    code: str
    name: str          # dotted full path
    width: int
    kind: str          # wire, reg, real, string, ...
    range: str = ""    # "[7:0]" or ""


@dataclass
class Header:
    lines: list[str]                      # header text up to and including $enddefinitions
    timescale: str = "1s"
    vars: list[Var] = field(default_factory=list)

    def match(self, regex: str | re.Pattern | None) -> list[Var]:
        if regex is None:
            return list(self.vars)
        try:
            rx = re.compile(regex) if isinstance(regex, str) else regex
        except re.error as exc:
            raise WaveError(f'invalid signal regex: {exc}') from exc
        return [v for v in self.vars if rx.search(v.name)]


class WaveError(Exception):
    pass


class _UnterminatedInitialDumpvars(WaveError):
    """Strict-reader error for exactly '#T $dumpvars <values> EOF'."""


def tool(name: str) -> str | None:
    """Find a GTKWave helper (fst2vcd, vcd2fst) on PATH."""
    active = _current.get()
    if active is not None and name in active.tool_names:
        return active.tool_names[name]
    selected = shutil.which(name, path=active.environment.get('PATH')) if active else shutil.which(name)
    if active is not None:
        selected = active.program(selected) if selected else None
        active.tool_names[name] = selected
    return selected


@contextlib.contextmanager
def open_text(path: str) -> Iterator[TextIO]:
    """Open a .vcd, .vcd.gz or .fst file as a VCD text stream."""
    if path.endswith(".fst"):
        exe = tool("fst2vcd")
        if not exe:
            raise WaveError("reading FST needs fst2vcd (GTKWave / oss-cad-suite) on PATH")
        # Disk-backed output bounds memory and lets run_group own cancellation and errors.
        with tempfile.TemporaryFile(mode="w+t") as converted:
            result = run_group([exe, path], stdout=converted, capture=False,
                               stderr=subprocess.PIPE, env=_current.get().environment if _current.get() else None)
            if result.returncode:
                raise WaveError(f"fst2vcd failed: {result.stderr or result.returncode}")
            _finish_fst_conversion(converted)
            yield converted
    elif path.endswith(".gz"):
        with gzip.open(path, "rt") as f:
            yield f
    else:
        with open(path, "r", buffering=1 << 20, errors="replace") as f:
            yield f


def _tokens(f: TextIO, first: list[str], lines: list[str] | None) -> Iterator[str]:
    yield from first
    header = True
    for line in f:
        if header and lines is not None:
            lines.append(line)
        for tok in line.split():
            if tok == "$enddefinitions":
                header = False
            yield tok


def read_header(f: TextIO, *, tokens: Iterator[str] | None = None) -> Header:
    """Parse declarations. Retain remaining tokens for body_records, even on the same line."""
    lines: list[str] = []
    hdr = Header(lines)
    scope: list[str] = []
    toks = tokens if tokens is not None else _tokens(f, [], lines)
    f._rvw_vcd_tokens = toks
    for tok in toks:
        if tok == "$scope":
            next(toks)                      # scope kind
            scope.append(next(toks))
            _skip_end(toks)
        elif tok == "$upscope":
            if scope:
                scope.pop()
            _skip_end(toks)
        elif tok == "$var":
            body = _until_end(toks)         # kind width code name [range]
            if len(body) < 4:
                continue
            kind, width, code, name = body[0], body[1], body[2], body[3]
            rng = "".join(body[4:])
            # Brackets in the reference token are part of its identity (e.g. \a[0]).
            # Only tokens after the reference declare a bit range.
            hdr.vars.append(Var(code, ".".join(scope + [name]), int(width) if width.isdigit() else 1,
                                kind, rng))
        elif tok == "$timescale":
            hdr.timescale = "".join(_until_end(toks))
        elif tok == "$enddefinitions":
            _skip_end(toks)
            f._rvw_vcd_codes = {v.code for v in hdr.vars}
            return hdr
        elif tok.startswith("$") and tok != "$end":
            _skip_end(toks)
    raise WaveError("no $enddefinitions: not a VCD file?")


def _until_end(toks: Iterator[str]) -> list[str]:
    out = []
    for t in toks:
        if t == "$end":
            return out
        out.append(t)
    raise WaveError("unterminated VCD directive")


def _skip_end(toks: Iterator[str]) -> None:
    _until_end(toks)


def body_records(f: TextIO) -> Iterator[tuple[int, str | None, str | None]]:
    """Read whitespace-separated records. A timestamp has code/value None.

    Scalar, binary, real and string changes and standard dump directives are supported.
    Unknown directives, invalid records and decreasing timestamps raise WaveError.
    The header token stream is retained, including body tokens on its final line.
    """
    toks = getattr(f, "_rvw_vcd_tokens", None)
    if toks is None:
        toks = (tok for line in f for tok in line.split())
    declared = getattr(f, "_rvw_vcd_codes", None)

    def identifier(code):
        if (not code or not all(33 <= ord(ch) <= 126 for ch in code)
                or (declared is not None and code not in declared)):
            raise WaveError(f"invalid or undeclared VCD identifier: {code}")
        return code

    now = None
    dump = False
    records = values = 0
    initial_dumpvars = False
    for tok in toks:
        records += 1
        c = tok[0]
        if c == "#":
            if dump or not re.fullmatch(r"#[0-9]+", tok):
                raise WaveError(f"invalid VCD timestamp: {tok}")
            t = int(tok[1:])
            if now is not None and t < now:
                raise WaveError("VCD timestamps decrease")
            now = t
            yield now, None, None
        elif tok == "$comment":
            initial_dumpvars = False
            _skip_end(toks)
        elif tok in ("$dumpvars", "$dumpall", "$dumpon", "$dumpoff"):
            if dump:
                raise WaveError("nested VCD dump directive")
            dump = True
            initial_dumpvars = tok == "$dumpvars" and records == 2 and now is not None
        elif tok == "$end":
            if not dump:
                raise WaveError("unexpected VCD $end")
            dump = False
        elif c in "01xzXZ":
            if len(tok) < 2:
                raise WaveError(f"missing VCD scalar identifier: {tok}")
            values += 1
            yield now if now is not None else 0, identifier(tok[1:]), c.lower()
        elif c in "bBrRsS":
            raw = tok
            if c in "bB" and not re.fullmatch(r"[bB][01xXzZ]+", raw):
                raise WaveError(f"invalid VCD binary value: {raw}")
            if c in "rR":
                try:
                    float(raw[1:])
                except ValueError:
                    raise WaveError(f"invalid VCD real value: {raw}") from None
            code = identifier(next(toks, None))
            values += 1
            yield now if now is not None else 0, code, raw
        else:
            raise WaveError(f"unsupported VCD record: {tok}")
    if dump:
        if initial_dumpvars and values:
            raise _UnterminatedInitialDumpvars("unterminated VCD dump directive")
        raise WaveError("unterminated VCD dump directive")


def _finish_fst_conversion(f: TextIO) -> None:
    """Validate converter output and close its known single-timestamp dumpvars EOF form.

    The strict reader still rejects this form for direct VCD inputs. No other syntax error,
    dump directive or multi-timestamp truncation is repaired, even after a converter exit 0.
    """
    f.seek(0)
    read_header(f)
    try:
        for _ in body_records(f):
            pass
    except _UnterminatedInitialDumpvars:
        f.seek(0, os.SEEK_END)
        f.write("\n$end\n")
    f.seek(0)
    del f._rvw_vcd_tokens
    del f._rvw_vcd_codes


def body_changes(f: TextIO, codes: set[str] | None = None, t0: int = 0,
                 t1: int | None = None) -> Iterator[tuple[int, str, str]]:
    """Yield (time, code, raw value) changes in the inclusive window."""
    for now, code, raw in body_records(f):
        if t1 is not None and now > t1:
            return
        if code is not None and now >= t0 and (codes is None or code in codes):
            yield now, code, raw


def state_at(f: TextIO, t: int, codes: set[str] | None = None) -> tuple[dict[str, str], int]:
    """Return ({code: raw value}, last timestamp) at or before t."""
    vals: dict[str, str] = {}
    last = 0
    for now, code, raw in body_records(f):
        if now > t:
            break
        last = now
        if code is not None and (codes is None or code in codes):
            vals[code] = raw
    return vals, last


def fmt_value(raw: str, width: int = 1, radix: str = "hex") -> str:
    """Format a raw VCD value: scalars as-is, vectors in hex (or 'b0x1z...' if not fully known)."""
    if len(raw) == 1:
        return raw
    if raw and raw[0] in "rRsS":
        return raw[1:]
    bits = raw[1:] if raw[:1] in "bB" else raw
    if bits and all(ch in "01" for ch in bits):
        v = int(bits, 2)
        return str(v) if radix == "dec" else hex(v)
    return "b" + bits.lower()


def to_int(raw: str | None) -> int | None:
    """Integer value of a raw VCD value, or None if unknown/absent."""
    if raw is None:
        return None
    bits = raw[1:] if raw[:1] in "bB" else raw
    if bits and all(ch in "01" for ch in bits):
        return int(bits, 2)
    return None


@captured
def end_time(path: str) -> int | None:
    """Last timestamp, using the same record reader as all other wave queries.

    Headerless body fragments are accepted here for tail-reader callers.
    """
    last = None
    with open_text(path) as f:
        # Detect a header without seeking (FST conversion may use a stream).
        first = []
        for line in f:
            first.extend(line.split())
            if first:
                break
        toks = _tokens(f, first, None)
        f._rvw_vcd_tokens = toks
        if first and first[0].startswith("$") and first[0] not in (
                "$dumpvars", "$dumpall", "$dumpon", "$dumpoff"):
            read_header(f, tokens=toks)
        for t, code, _ in body_records(f):
            if code is None:
                last = t
    return last


def write_value(out: io.TextIOBase, raw: str, code: str) -> None:
    if len(raw) == 1 and raw in "01xz":
        out.write(f"{raw}{code}\n")
    else:
        out.write(f"{raw} {code}\n")
