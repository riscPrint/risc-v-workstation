"""Select replay states by declared coverage-hole targets, bound to trace bytes."""
from hashlib import sha256
import json
from pathlib import Path


def select(path, trace, first, last, count):
    raw = Path(path).read_bytes()
    plan = json.loads(raw)
    if plan['trace_sha256'] != sha256(Path(trace).read_bytes()).hexdigest():
        raise ValueError('state plan trace hash mismatch')
    holes = plan['holes']
    if not holes or any(not isinstance(h, str) or not h for h in holes) or len(set(holes)) != len(holes):
        raise ValueError('state plan needs unique nonempty coverage hole IDs')
    candidates = {}
    for state in plan['states']:
        cycle, targets = state['cycle'], state['targets']
        if type(cycle) is not int or cycle < 1 or cycle in candidates:
            raise ValueError('state plan cycles must be unique positive integers')
        if not set(targets) <= set(holes):
            raise ValueError('state target is not a declared coverage hole')
        candidates[cycle] = set(targets)
    pool = {c: t for c, t in candidates.items() if first <= c <= last}
    if count < 1 or len(pool) < count:
        raise ValueError('not enough eligible state-plan cycles')
    remaining, chosen = set(holes), []
    for _ in range(count):
        cycle = min(pool, key=lambda c: (-len(pool[c] & remaining), c))
        chosen.append(cycle)
        remaining -= pool.pop(cycle)
    return chosen, {'method': 'declared_coverage_holes', 'cycles': chosen,
                    'plan_sha256': sha256(raw).hexdigest(), 'trace_sha256': plan['trace_sha256'],
                    'holes': holes, 'unrepresented_targets': sorted(remaining),
                    'limits': 'Targets are supplied priorities. Selection does not prove that a cover is reachable.'}
