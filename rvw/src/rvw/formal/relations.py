"""Trace-derived bit-vector relations. Native proofs must certify every candidate."""
from itertools import combinations
from .mining import candidates as bounds


def candidates(signals, samples):
    result = bounds(signals, samples)
    for a, b in combinations(sorted(signals), 2):
        pairs = [(s[a], s[b]) for s in samples]
        prefix = 'rel_' + a + '_' + b
        if all(x == y for x, y in pairs):
            result[prefix + '_eq'] = f'({a} == {b})'
        if all(x <= y for x, y in pairs):
            result[prefix + '_le'] = f'({a} <= {b})'
        if all(not x or not y for x, y in pairs):
            result[prefix + '_exclusive'] = f'!(({a} != 0) && ({b} != 0))'
        delta = pairs[0][0] - pairs[0][1]
        if delta and all(x - y == delta for x, y in pairs):
            # The proof checks Verilog bit-vector arithmetic, including overflow.
            result[prefix + '_offset'] = f'({a} == ({b} + {delta}))' if delta > 0 else f'({b} == ({a} + {-delta}))'
    return result


def run(args):
    from .mining import run as strengthen
    return strengthen(args, candidate_builder=candidates)
