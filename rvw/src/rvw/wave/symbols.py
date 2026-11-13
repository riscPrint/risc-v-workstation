"""ELF symbols joined with wave values: name PC values and profile time per function.

Symbols come from the ELF symbol table (standard library reader, no toolchain). A PC maps to
the sized symbol that contains it. A PC outside every sized symbol has no symbol; it is never
assigned to the nearest label.
"""
from __future__ import annotations

import bisect
import re

from .expr import Expr, value_of
from .ops import CLOCK_RX
from .search import _validate, open_wave
from .vcd import WaveError


class Symbols:
    def __init__(self, elf: str):
        from ..runs.elf import Elf
        try:
            syms = Elf(elf).symbols().values()
        except (OSError, ValueError) as exc:
            raise WaveError(f'cannot read ELF symbols: {exc}') from exc
        spans = sorted((s.value, s.value + s.size, s.name) for s in syms if s.size and s.shndx)
        self.starts = [a for a, _, _ in spans]
        self.spans = spans
        self.elf = elf

    def lookup(self, pc: int) -> dict | None:
        i = bisect.bisect_right(self.starts, pc) - 1
        # Sized symbols can nest (a local label inside a function): take the innermost.
        while i >= 0:
            start, end, name = self.spans[i]
            if start <= pc < end:
                return {'symbol': name, 'offset': pc - start}
            if pc - start > 1 << 24:
                break
            i -= 1
        return None


def annotate_changes(page: dict, elf: str, pc_regex: str = r'(?i)pc') -> dict:
    """Add `symbol` (`name+0xoff`) to `changes` rows of PC-like signals (`pc_regex`)."""
    syms = Symbols(elf)
    rx = re.compile(pc_regex)
    for row in page.get('changes', []):
        if not rx.search(row['signal']):
            continue
        try:
            pc = int(row['value'], 0)
        except (TypeError, ValueError):
            continue
        hit = syms.lookup(pc)
        if hit:
            row['symbol'] = f"{hit['symbol']}+{hit['offset']:#x}"
    return page


def profile(path: str, pc: str, elf: str, valid: str | None = None, t0: int = 0, t1: int | None = None,
            clock: str = CLOCK_RX, phases: int = 50) -> dict:
    """Clock edges per function: at each rising edge (pre-edge values) where `valid` holds
    (every edge without it), the PC signal's value is mapped to its symbol.

    `phases` lists the first runs of consecutive edges in one function (time-aligned segments).
    Unknown PC values count as `unknown`; PCs outside every symbol count as `(no symbol)`.
    """
    from .temporal import pick_clock, sampled
    from .expr import resolve
    _validate(t0, t1)
    syms = Symbols(elf)
    counts: dict[str, int] = {}
    runs: list[dict] = []
    total = unknown = 0
    with open_wave(path) as src:
        pv = resolve(pc, src.hdr.vars)
        ex = Expr(valid, src.hdr.vars) if valid else None
        clk = pick_clock(src.hdr, clock)
        codes = {pv.code} | (ex.codes if ex else set())
        prev: dict = {}
        current = None
        for t, vals in sampled(src, clk, codes, t0, t1):
            ok = ex.evaluate(vals, prev) if ex else True
            prev = vals
            if not ok:
                continue
            total += 1
            value = value_of(vals.get(pv.code))
            if value is None or not isinstance(value, int):
                unknown += 1
                name = 'unknown'
            else:
                hit = syms.lookup(value)
                name = hit['symbol'] if hit else '(no symbol)'
            counts[name] = counts.get(name, 0) + 1
            if current is not None and current['function'] == name:
                current['end'] = t
                current['edges'] += 1
            else:
                current = {'function': name, 'start': t, 'end': t, 'edges': 1}
                if len(runs) < phases:
                    runs.append(current)
                else:
                    current = dict(current)      # keep counting, but do not list it
    rows = sorted(({'function': k, 'edges': v, 'fraction': v / total} for k, v in counts.items()),
                  key=lambda r: (-r['edges'], r['function']))
    return {'pc': pv.name, 'valid': valid, 'clock': clk.name, 'elf': elf, 'from': t0, 'to': t1,
            'edges': total, 'unknown': unknown, 'functions': rows, 'phases': runs,
            'basis': 'edges where valid holds, by the PC symbol in the ELF symbol table; not a cycle-accurate '
                     'attribution of stalls to functions'}
