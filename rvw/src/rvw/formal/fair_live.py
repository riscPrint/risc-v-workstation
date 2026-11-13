"""Exact recurrent-progress checks on an explicit finite transition graph."""
from .deep_model import validate, adjacency


def components(edges):
    """Iterative Kosaraju decomposition avoids recursion limits on large graphs."""
    seen, order = set(), []
    for start in edges:
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(edges[start]))]
        while stack:
            node, children = stack[-1]
            nxt = next(children, None)
            if nxt is None:
                order.append(node)
                stack.pop()
            elif nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, iter(edges[nxt])))
    reverse = {s: set() for s in edges}
    for s, targets in edges.items():
        for t in targets:
            reverse[t].add(s)
    seen = set()
    for start in reversed(order):
        if start in seen:
            continue
        part, pending = set(), [start]
        seen.add(start)
        while pending:
            s = pending.pop()
            part.add(s)
            for t in reverse[s] - seen:
                seen.add(t)
                pending.append(t)
        yield part


def check(model, progress, fairness=()):
    """Check GF progress under generalized Buchi state-justice constraints.

    Each fairness state set must recur infinitely. Finite deadlock paths do not
    count as infinite executions; they are reported separately.
    """
    validate(model)
    states = set(model['states'])
    progress, fairness = set(progress), [set(f) for f in fairness]
    if not progress <= states or any(not f <= states for f in fairness):
        raise ValueError('progress and fairness need known states')
    edges = adjacency(model)
    reachable, pending = set(model['initial']), list(model['initial'])
    while pending:
        for t in edges[pending.pop()] - reachable:
            reachable.add(t)
            pending.append(t)
    def fair_cycles(nodes):
        graph = {s: edges[s] & nodes for s in nodes}
        return [sorted(c) for c in components(graph)
                if (len(c) > 1 or any(s in graph[s] for s in c))
                and all(c & f for f in fairness)]
    feasible = fair_cycles(reachable)
    bad = fair_cycles(reachable - progress)
    status = 'fail' if bad else 'pass' if feasible else 'inconclusive'
    return {'schema': 'rvw.formal-model-live/1', 'status': status,
            'proof_kind': 'finite_graph_fair_liveness' if status == 'pass' else 'none',
            'fairness': [sorted(f) for f in fairness], 'progress': sorted(progress),
            'reachable_states': len(reachable), 'fair_cycle_components': feasible,
            'counterexample_components': bad, 'deadlocks': sorted(s for s in reachable if not edges[s]),
            'reason': 'fair_nonprogress_cycle' if bad else 'progress_on_all_fair_paths' if feasible else 'no_fair_infinite_execution',
            'limits': 'Exact supplied finite graph only. No RTL translation claim. '
                      'Fairness is an explicit conditional assumption. Finite deadlocks are not infinite paths.'}
