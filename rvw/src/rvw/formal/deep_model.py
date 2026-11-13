"""Exact safety algorithms for explicit finite transition systems.

The supplied graph is the model, not a proof of an RTL-to-model translation.
Memory words and counters are integer state fields. Edges include all choices.
"""
from collections import deque
from itertools import combinations


def validate(model):
    states = model['states']
    if not states or not model['initial'] or not set(model['initial']) <= states.keys():
        raise ValueError('model needs states and initial states')
    fields = set(next(iter(states.values())))
    if any(set(s) != fields or any(type(v) is not int for v in s.values()) for s in states.values()):
        raise ValueError('states need the same integer fields')
    for a, b in model['edges']:
        if a not in states or b not in states:
            raise ValueError('unknown transition endpoint')
    if not model['properties'] or any(not set(bad) <= states.keys() for bad in model['properties'].values()):
        raise ValueError('properties need known bad states')
    return fields


def adjacency(model):
    result = {s: set() for s in model['states']}
    for a, b in model['edges']:
        result[a].add(b)
    return result


def path_to_bad(initial, edges, bad):
    parent = {s: None for s in initial}
    queue = deque(initial)
    while queue:
        s = queue.popleft()
        if s in bad:
            trace = []
            while s is not None:
                trace.append(s)
                s = parent[s]
            return trace[::-1]
        for t in edges[s]:
            if t not in parent:
                parent[t] = s
                queue.append(t)
    return None


def mine(model, samples):
    """Keep a trace candidate only after exact initiation and consecution checks."""
    fields = sorted(validate(model))
    if not samples:
        return []
    if any(set(s) != set(fields) or any(type(v) is not int for v in s.values()) for s in samples):
        raise ValueError('trace samples need every integer state field')
    predicates = []
    for f in fields:
        lo, hi = min(s[f] for s in samples), max(s[f] for s in samples)
        predicates.append((f'{lo} <= {f} <= {hi}', lambda s, f=f, lo=lo, hi=hi: lo <= s[f] <= hi))
    for a, b in combinations(fields, 2):
        delta = samples[0][a] - samples[0][b]
        if all(s[a] - s[b] == delta for s in samples):
            predicates.append((f'{a} - {b} == {delta}', lambda s, a=a, b=b, d=delta: s[a] - s[b] == d))
        if all(s[a] <= s[b] for s in samples):
            predicates.append((f'{a} <= {b}', lambda s, a=a, b=b: s[a] <= s[b]))
    rows = []
    for expr, pred in predicates:
        good = {s for s, v in model['states'].items() if pred(v)}
        # Independent certification prevents circular helper assumptions.
        certified = set(model['initial']) <= good and all(a not in good or b in good for a, b in model['edges'])
        rows.append({'expression': expr, 'status': 'proven' if certified else 'rejected',
                     'states': sorted(good) if certified else []})
    return rows


def induction(model, prop, max_k=8, samples=()):
    """Base and k-step checks over all model states, with certified helpers only."""
    validate(model)
    if max_k < 1:
        raise ValueError('max_k must be positive')
    edges = adjacency(model)
    bad = set(model['properties'][prop])
    helpers = mine(model, samples)
    allowed = set(model['states'])
    for row in helpers:
        if row['status'] == 'proven':
            allowed &= set(row['states'])
    good = allowed - bad
    base = set(model['initial'])
    # ends contains endpoints of paths with k consecutive good states.
    ends = set(good)
    for k in range(1, max_k + 1):
        if base & bad:
            return {'status': 'fail', 'proof_kind': 'counterexample', 'k': k,
                    'trace': path_to_bad(model['initial'], edges, bad), 'helpers': helpers}
        successors = {t for s in ends for t in edges[s] if t in allowed}
        base |= {t for s in base for t in edges[s]}
        if base & bad:
            return {'status': 'fail', 'proof_kind': 'counterexample', 'k': k,
                    'trace': path_to_bad(model['initial'], edges, bad), 'helpers': helpers}
        if not successors & bad:
            return {'status': 'pass', 'proof_kind': 'unbounded', 'k': k, 'helpers': helpers}
        ends = successors & good
    return {'status': 'inconclusive', 'proof_kind': 'bounded', 'k': max_k, 'helpers': helpers}


def abstract(model, prop, visible=(), max_refinements=None):
    """Existential projection, concrete trace replay, then state-field refinement.

    Omitting RAM words gives a nondeterministic RAM abstraction. Omitting counter
    fields gives a counter abstraction. No read/collision/init choice is invented.
    """
    fields = validate(model)
    visible = set(visible)
    if not visible <= fields:
        raise ValueError('unknown visible field')
    if max_refinements is None:
        max_refinements = len(fields)
    if max_refinements < 0:
        raise ValueError('max_refinements must be nonnegative')
    bad = set(model['properties'][prop])
    concrete_edges = adjacency(model)
    rounds = []
    for iteration in range(max_refinements + 1):
        names = sorted(visible)
        project = {s: tuple(v[f] for f in names) for s, v in model['states'].items()}
        edges = {v: set() for v in project.values()}
        for a, b in model['edges']:
            edges[project[a]].add(project[b])
        trace = path_to_bad({project[s] for s in model['initial']}, edges, {project[s] for s in bad})
        row = {'visible': names, 'abstract_states': len(edges)}
        rounds.append(row)
        if trace is None:
            row['status'] = 'proven'
            return {'status': 'pass', 'proof_kind': 'unbounded', 'rounds': rounds}
        reachable = {s for s in model['initial'] if project[s] == trace[0]}
        for group in trace[1:]:
            reachable = {t for s in reachable for t in concrete_edges[s] if project[t] == group}
        if reachable & bad:
            row['status'] = 'concrete_counterexample'
            return {'status': 'fail', 'proof_kind': 'counterexample', 'rounds': rounds,
                    'trace': path_to_bad(model['initial'], concrete_edges, bad)}
        row['status'] = 'spurious'
        omitted = sorted(fields - visible)
        if not omitted or iteration == max_refinements:
            return {'status': 'inconclusive', 'proof_kind': 'abstraction', 'reason': 'spurious', 'rounds': rounds}
        # Prefer a field that splits a currently merged equivalence class.
        selected = next((f for f in omitted if any(
            project[a] == project[b] and model['states'][a][f] != model['states'][b][f]
            for a, b in combinations(model['states'], 2))), omitted[0])
        row['refine'] = selected
        visible.add(selected)
