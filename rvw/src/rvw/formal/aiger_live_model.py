"""AIGER justice models and finite-state liveness safety reductions.

A justice group is a bad generalized Buchi condition: every member recurs.
Fairness literals must also recur. No source-language translation is done here.
"""
from dataclasses import dataclass
import re


@dataclass
class Model:
    inputs: list
    latches: list
    gates: list
    constraints: list
    justice: list
    fairness: list


def read(text):
    """Read ASCII AIGER 1.9 with exactly one pure justice property."""
    lines = iter(text.splitlines())
    header = next(lines, '').split()
    if not 6 <= len(header) <= 10 or header[0] != 'aag':
        raise ValueError('liveness requires ASCII AIGER (aag)')
    counts = [int(x) for x in header[1:]]
    counts += [0] * (9 - len(counts))
    m, ni, nl, no, na, nb, nc, nj, nf = counts
    if min(counts) < 0 or no or nb or nj != 1:
        raise ValueError('require one justice group, no outputs and no safety properties')
    def values(size):
        line = next(lines, '').split()
        if len(line) != size:
            raise ValueError('truncated or invalid AIGER record')
        return [int(x) for x in line]
    inputs = [values(1)[0] for _ in range(ni)]
    latches = []
    for _ in range(nl):
        row = next(lines, '').split()
        if len(row) not in (2, 3):
            raise ValueError('invalid AIGER latch')
        q, nxt = map(int, row[:2])
        init = int(row[2]) if len(row) == 3 else 0
        if init not in (0, 1, q):
            raise ValueError('invalid AIGER initialization')
        latches.append((q, nxt, init))
    constraints = [values(1)[0] for _ in range(nc)]
    size = values(1)[0]
    if size < 1:
        raise ValueError('empty justice group')
    # AIGER writes justice sizes, justice literals, fairness, then AND gates.
    justice = [values(1)[0] for _ in range(size)]
    fairness = [values(1)[0] for _ in range(nf)]
    gates = [values(3) for _ in range(na)]
    defined = {0}
    for literal in inputs + [q for q, _, _ in latches] + [g[0] for g in gates]:
        if literal <= 1 or literal % 2 or literal > 2 * m or literal // 2 in defined:
            raise ValueError('duplicate or invalid AIGER variable')
        defined.add(literal // 2)
    refs = constraints + justice + fairness + [n for _, n, _ in latches]
    available = {0, *inputs, *(q for q, _, _ in latches)}
    for lhs, a, b in gates:
        if any(x < 0 or x >= lhs or (x & ~1) not in available for x in (a, b)):
            raise ValueError('undefined or non-topological AIGER gate')
        available.add(lhs)
        refs.extend((a, b))
    if any(x < 0 or x // 2 not in defined for x in refs):
        raise ValueError('undefined AIGER literal')
    for line in lines:
        if line == 'c':
            break
        match = re.fullmatch(r'([ilcjf])(\d+) (.+)', line)
        if not match or int(match[2]) >= {'i': ni, 'l': nl, 'c': nc, 'j': nj, 'f': nf}[match[1]]:
            raise ValueError('invalid AIGER symbol footer')
    return Model(inputs, latches, gates, constraints, justice, fairness)


class Builder:
    def __init__(self, inputs, latches):
        self.inputs = [2 * (i + 1) for i in range(inputs)]
        self.q = [2 * (inputs + i + 1) for i in range(latches)]
        self.next = self.q.copy()
        self.init = [0] * latches
        self.maximum = inputs + latches
        self.gates, self.cache, self.constraints = [], {}, []

    def and_(self, a, b):
        if 0 in (a, b) or a == b ^ 1:
            return 0
        if a == 1 or a == b:
            return b
        if b == 1:
            return a
        key = tuple(sorted((a, b), reverse=True))
        if key not in self.cache:
            self.maximum += 1
            self.cache[key] = 2 * self.maximum
            self.gates.append((2 * self.maximum, *key))
        return self.cache[key]

    def all(self, terms):
        value = 1
        for term in terms:
            value = self.and_(value, term)
        return value

    def or_(self, a, b):
        return self.and_(a ^ 1, b ^ 1) ^ 1

    def xor(self, a, b):
        return self.or_(self.and_(a, b ^ 1), self.and_(a ^ 1, b))

    def mux(self, cond, yes, no):
        return self.or_(self.and_(cond, yes), self.and_(cond ^ 1, no))

    def text(self, bad):
        lines = [f'aag {self.maximum} {len(self.inputs)} {len(self.q)} 0 {len(self.gates)} 1 {len(self.constraints)} 0 0']
        lines += [str(i) for i in self.inputs]
        lines += [f'{q} {n} {init}' for q, n, init in zip(self.q, self.next, self.init)]
        lines += [str(bad)] + [str(c) for c in self.constraints]
        lines += [' '.join(map(str, g)) for g in self.gates]
        return '\n'.join(lines) + '\nc\nrvw finite-state justice reduction\n'


def copy_model(model, extra_inputs, extra_latches):
    builder = Builder(len(model.inputs) + extra_inputs, len(model.latches) + extra_latches)
    mapping = {0: 0}
    mapping.update(zip(model.inputs, builder.inputs))
    mapping.update((row[0], q) for row, q in zip(model.latches, builder.q))
    def lit(value):
        return mapping[value & ~1] ^ (value & 1)
    for lhs, a, b in model.gates:
        mapping[lhs] = builder.and_(lit(a), lit(b))
    for i, (q, nxt, init) in enumerate(model.latches):
        builder.next[i] = lit(nxt)
        builder.init[i] = builder.q[i] if init == q else init
    builder.constraints = [lit(c) for c in model.constraints]
    return builder, lit


def reduce(model, method='l2s', k=2, *, feasibility=False):
    """Reduce existence of a fair accepting infinite path to safety reachability.

    L2S captures one source state and records all goals over a nonempty loop.
    K-liveness is sufficient only: reaching k complete rounds is inconclusive.
    """
    if method not in ('l2s', 'k-live'):
        raise ValueError('method must be l2s or k-live')
    goals = (model.fairness or [1]) if feasibility else model.justice + model.fairness
    nl, ng = len(model.latches), len(goals)
    if method == 'l2s':
        builder, lit = copy_model(model, 1, nl + 1 + ng)
        saved = builder.q[nl:2 * nl]
        tracking = builder.q[2 * nl]
        seen = builder.q[2 * nl + 1:]
        capture = builder.and_(builder.inputs[-1], tracking ^ 1)
        active = builder.or_(tracking, capture)
        for i, (q, old) in enumerate(zip(builder.q[:nl], saved)):
            builder.next[nl + i] = builder.mux(capture, q, old)
        builder.next[2 * nl] = active
        for i, (flag, goal) in enumerate(zip(seen, goals)):
            builder.next[2 * nl + 1 + i] = builder.and_(active, builder.or_(flag, lit(goal)))
        equal = [builder.xor(q, old) ^ 1 for q, old in zip(builder.q[:nl], saved)]
        bad = builder.all([tracking, *seen, *equal])
    else:
        if type(k) is not int or not 1 <= k <= 1024:
            raise ValueError('k must be in 1..1024')
        width = k.bit_length()
        builder, lit = copy_model(model, 0, ng + width)
        seen, counter = builder.q[nl:nl + ng], builder.q[nl + ng:]
        observed = [builder.or_(q, lit(goal)) for q, goal in zip(seen, goals)]
        complete = builder.all(observed)
        for i, value in enumerate(observed):
            builder.next[nl + i] = builder.and_(value, complete ^ 1)
        carry = 1
        for i, q in enumerate(counter):
            increment = builder.xor(q, carry)
            carry = builder.and_(carry, q)
            builder.next[nl + ng + i] = builder.mux(complete, increment, q)
        bad = builder.all(q if k & (1 << i) else q ^ 1 for i, q in enumerate(counter))
    return builder.text(bad), {'method': method, 'k': k if method == 'k-live' else None,
                              'source_latches': nl, 'reduced_latches': len(builder.q),
                              'goals': goals, 'feasibility': feasibility}
