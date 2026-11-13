"""Finite weak-fairness SCC checks for coherence transition graphs."""
from collections import deque


def components(graph):
    """Iterative Kosaraju SCC decomposition. Graph values are (action, state)."""
    visited, order = set(), []
    for root in graph:
        if root in visited:
            continue
        visited.add(root)
        stack = [(root, iter(n for _, n in graph[root]))]
        while stack:
            state, edges = stack[-1]
            nxt = next(edges, None)
            if nxt is None:
                order.append(state)
                stack.pop()
            elif nxt not in visited:
                visited.add(nxt)
                stack.append((nxt, iter(n for _, n in graph[nxt])))
    reverse = {s: [] for s in graph}
    for s, edges in graph.items():
        for _, n in edges:
            reverse[n].append(s)
    visited.clear()
    for root in reversed(order):
        if root in visited:
            continue
        group, stack = set(), [root]
        visited.add(root)
        while stack:
            state = stack.pop()
            group.add(state)
            for previous in reverse[state]:
                if previous not in visited:
                    visited.add(previous)
                    stack.append(previous)
        yield group


def fair_cycle(graph, pending, fairness):
    """Find a pending-request SCC with a weakly fair infinite execution.

    Each named assumption maps to a set of transition labels. If the set is
    enabled in every SCC state, at least one matching transition must stay in
    that SCC. Otherwise a tour of the SCC can disable it infinitely often.
    Every pending state has an environment stutter edge. This is finite weak fairness, not
    strong fairness and not an unbounded RTL liveness result.
    """
    if not fairness or any(not name or not labels for name, labels in fairness.items()):
        raise ValueError('named nonempty fairness action sets required')
    restricted = {s: [(a, n) for a, n in edges if pending(n)]
                  for s, edges in graph.items() if pending(s)}
    for state, edges in restricted.items():
        edges.append(('stutter', state))
    for group in components(restricted):
        if len(group) == 1:
            s = next(iter(group))
            if not any(n == s for _, n in restricted[s]):
                continue
        internal = {a for s in group for a, n in restricted[s] if n in group}
        unfair = []
        for name, labels in fairness.items():
            continuously_enabled = all(any(a in labels for a, _ in graph[s]) for s in group)
            if continuously_enabled and not internal.intersection(labels):
                unfair.append(name)
        if not unfair:
            return {'states': group, 'internal_actions': sorted(internal)}
    return None


def explore(root, successors, invariant, complete, targets, fairness, limit=100000):
    """Exhaust a finite model before checking each named request target."""
    if limit < 1 or not targets:
        raise ValueError('positive state budget and named progress targets required')
    queue, parent, graph = deque([root]), {root: None}, {}
    report = {'schema': 'rvw.coherence-fair/1', 'status': 'inconclusive',
              'fairness': {k: sorted(v) for k, v in fairness.items()},
              'progress': 'finite weak fairness', 'states': 1, 'exhaustive_rtl_proof': False}
    def path(state):
        result = []
        while parent[state] is not None:
            state, action = parent[state]
            result.append(action)
        return list(reversed(result))
    while queue:
        s = queue.popleft()
        error = invariant(s)
        if error:
            return report | {'status': 'fail', 'failure': error, 'witness': path(s), 'states': len(parent)}
        graph[s] = [] if complete(s) else list(successors(s))
        for action, nxt in graph[s]:
            if nxt not in parent:
                if len(parent) >= limit:
                    return report | {'reason': 'state_limit', 'states': len(parent)}
                parent[nxt] = s, action
                queue.append(nxt)
    for name, pending in targets.items():
        cycle = fair_cycle(graph, pending, fairness)
        if cycle:
            entry = min(cycle['states'], key=repr)
            return report | {'status': 'fail', 'failure': 'fair_noncompletion', 'target': name,
                             'states': len(parent), 'witness': path(entry),
                             'scc_states': len(cycle['states']), 'scc_actions': cycle['internal_actions']}
    return report | {'status': 'pass', 'states': len(parent)}
