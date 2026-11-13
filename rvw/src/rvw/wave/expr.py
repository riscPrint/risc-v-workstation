"""Signal expressions for wave searches.

An expression is a small Python/Verilog-like formula over signals:

    valid && ready && data[7:0] == 0x2a
    rose(TOP.Top.clk) and !reset
    `TOP.Top.mem[3]` != 0

Signal names are dotted paths. A name resolves to the exact full path, or to the one signal
whose path ends with `.NAME`. Ambiguous or unknown names are errors. Backticks quote names
that are not identifiers (array elements, escaped names).

Values use three-valued logic: x/z bits make a value unknown (None). An unknown operand makes
the result unknown unless `and`/`or` decide it. Only a known non-zero result counts as true.
"""
from __future__ import annotations

import ast
import re
from typing import Callable

from .vcd import Var, WaveError

FUNCS = ('rose', 'fell', 'changed', 'stable', 'known')


def value_of(raw: str | None):
    """Raw VCD value to int, float, str, or None for unknown/absent."""
    if raw is None:
        return None
    c = raw[0]
    if len(raw) == 1:
        return int(raw) if raw in '01' else None
    if c in 'rR':
        return float(raw[1:])
    if c in 'sS':
        return raw[1:]
    bits = raw[1:] if c in 'bB' else raw
    if bits and all(ch in '01' for ch in bits):
        return int(bits, 2)
    return None


def resolve(name: str, vars: list[Var]) -> Var:
    exact = [v for v in vars if v.name == name]
    if len(exact) == 1:
        return exact[0]
    found = exact or [v for v in vars if v.name.endswith('.' + name)]
    codes = {v.code for v in found}
    if not found:
        raise WaveError(f'no signal matches {name!r}')
    if len(codes) > 1:
        names = ', '.join(sorted(v.name for v in found)[:8])
        raise WaveError(f'signal name {name!r} is ambiguous: {names}')
    return found[0]


def _dotted(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f'{base}.{node.attr}' if base else None
    return None


def _and(vals):
    unknown = False
    for v in vals:
        x = v()
        if x is None:
            unknown = True
        elif not x:
            return False
    return None if unknown else True


def _or(vals):
    unknown = False
    for v in vals:
        x = v()
        if x is None:
            unknown = True
        elif x:
            return True
    return None if unknown else False


_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.FloorDiv: lambda a, b: a // b if b else None, ast.Mod: lambda a, b: a % b if b else None,
        ast.BitAnd: lambda a, b: a & b, ast.BitOr: lambda a, b: a | b, ast.BitXor: lambda a, b: a ^ b,
        ast.LShift: lambda a, b: a << b, ast.RShift: lambda a, b: a >> b}
_CMP = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b, ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b}


class _Bits(str):
    """Raw bit string (MSB first) of a signal read directly by a bit select."""


def _select(x, hi, lo, mask):
    if x is None:
        return None
    if isinstance(x, _Bits):
        width = len(x)
        bits = ''.join(x[width - 1 - i] if i < width else '0' for i in range(hi, lo - 1, -1))
        return int(bits, 2) if all(ch in '01' for ch in bits) else None
    if not isinstance(x, int):
        return None
    return (x >> lo) & mask


class Expr:
    """Compiled expression. Call `bind(state, prev)` once per evaluation point, then `value()`."""

    def __init__(self, text: str, vars: list[Var]):
        self.text = text
        quoted: dict[str, str] = {}

        def quote(m):
            key = f'__q{len(quoted)}'
            quoted[key] = m.group(1)
            return key
        src = re.sub(r'`([^`]+)`', quote, text)
        src = src.replace('&&', ' and ').replace('||', ' or ')
        src = re.sub(r'!(?!=)', ' not ', src)
        try:
            tree = ast.parse(src.strip(), mode='eval')
        except SyntaxError as exc:
            raise WaveError(f'invalid wave expression {text!r}: {exc.msg}') from exc
        self.vars: dict[str, Var] = {}      # name as written -> Var
        self._quoted = quoted
        self._all = vars
        self._state: dict = {}
        self._prev: dict = {}
        self._fn = self._compile(tree.body)

    @property
    def codes(self) -> set[str]:
        return {v.code for v in self.vars.values()}

    def _signal(self, name: str) -> Var:
        name = self._quoted.get(name, name)
        if name not in self.vars:
            self.vars[name] = resolve(name, self._all)
        return self.vars[name]

    def _compile(self, n) -> Callable:
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, str)) and not isinstance(n.value, bool):
            v = n.value
            return lambda: v
        name = _dotted(n)
        if name is not None:
            code = self._signal(name).code
            return lambda: self._state.get(code)
        if isinstance(n, ast.BoolOp):
            parts = [self._compile(x) for x in n.values]
            return (lambda: _and(parts)) if isinstance(n.op, ast.And) else (lambda: _or(parts))
        if isinstance(n, ast.UnaryOp):
            a = self._compile(n.operand)
            if isinstance(n.op, ast.Not):
                return lambda: None if (x := a()) is None else (not x)
            if isinstance(n.op, ast.Invert):
                width = self._width(n.operand)
                return lambda: None if (x := a()) is None else (~x) & ((1 << width) - 1)
            if isinstance(n.op, ast.USub):
                return lambda: None if (x := a()) is None else -x
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b, op = self._compile(n.left), self._compile(n.right), _BIN[type(n.op)]
            return lambda: None if (x := a()) is None or (y := b()) is None else op(x, y)
        if isinstance(n, ast.Compare):
            terms = [self._compile(n.left)] + [self._compile(c) for c in n.comparators]
            ops = [_CMP[type(o)] for o in n.ops if type(o) in _CMP]
            if len(ops) != len(n.ops):
                raise WaveError(f'unsupported comparison in {self.text!r}')

            def compare():
                vals = [t() for t in terms]
                if any(v is None for v in vals):
                    return None
                return all(op(vals[i], vals[i + 1]) for i, op in enumerate(ops))
            return compare
        if isinstance(n, ast.Subscript):
            a = self._compile(n.value)
            s = n.slice
            direct = _dotted(n.value)
            if direct is not None:
                # Select bits from the raw value, so known bits of a partly unknown vector stay known.
                code = self._signal(direct).code
                a = self._bits(code)
            if isinstance(s, ast.Slice) and isinstance(s.lower, ast.Constant) and isinstance(s.upper, ast.Constant):
                hi, lo = s.lower.value, s.upper.value
                if hi < lo:
                    hi, lo = lo, hi
                mask = (1 << (hi - lo + 1)) - 1
                return lambda: _select(a(), hi, lo, mask)
            if isinstance(s, ast.Constant) and isinstance(s.value, int):
                bit = s.value
                return lambda: _select(a(), bit, bit, 1)
            raise WaveError(f'bit selects need constant indexes in {self.text!r}')
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and len(n.args) == 1:
            name = _dotted(n.args[0])
            if name is None:
                raise WaveError(f'{n.func.id}() takes one signal name')
            code = self._signal(name).code
            st, pv = (lambda: self._state.get(code)), (lambda: self._prev.get(code))
            f = n.func.id
            if f == 'known':
                return lambda: st() is not None
            if f == 'rose':
                return lambda: None if (x := st()) is None or (y := pv()) is None else bool(x & 1 and not y & 1)
            if f == 'fell':
                return lambda: None if (x := st()) is None or (y := pv()) is None else bool(y & 1 and not x & 1)
            if f == 'changed':
                return lambda: self._raw.get(code) != self._raw_prev.get(code)
            return lambda: self._raw.get(code) == self._raw_prev.get(code)
        raise WaveError(f'unsupported wave expression syntax in {self.text!r}: {ast.dump(n)[:60]}')

    def _bits(self, code):
        def read():
            raw = self._raw.get(code)
            if raw is None or raw[:1] in ('r', 'R', 's', 'S'):
                return value_of(raw)
            return _Bits(raw[1:] if raw[:1] in 'bB' else raw)
        return read

    def _width(self, n) -> int:
        name = _dotted(n)
        return self._signal(name).width if name else 64

    def evaluate(self, raw: dict[str, str], raw_prev: dict[str, str]):
        """Evaluate with current and previous raw values ({code: raw})."""
        self._raw, self._raw_prev = raw, raw_prev
        self._state = {c: value_of(raw.get(c)) for c in self.codes}
        self._prev = {c: value_of(raw_prev.get(c)) for c in self.codes}
        return self._fn()

    def signals(self) -> dict[str, str]:
        return {k: v.name for k, v in self.vars.items()}
