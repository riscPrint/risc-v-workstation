"""Exhaustive small-state checks against the justice reductions."""
from collections import deque
from itertools import product
import pytest
from rvw.formal.aiger_live_model import read, reduce, Builder

pytestmark = pytest.mark.fast


def progress_model(kind='toggle', fairness=None, constraint=None):
    b = Builder(2, 3)
    choose, ready = b.inputs
    progress, armed, dead = b.q
    armed_next = b.or_(armed, choose)
    b.next = [progress ^ 1 if kind == 'toggle' else 0 if kind == 'stuck' else ready,
              armed_next, b.or_(dead, b.and_(armed_next, progress))]
    justice = b.and_(armed, dead ^ 1)
    fair = [] if fairness is None else [ready if fairness == 'ready' else 0]
    constraints = [] if constraint is None else [0 if constraint == 'false' else ready]
    lines = [f'aag {b.maximum} 2 3 0 {len(b.gates)} 0 {len(constraints)} 1 {len(fair)}',
             *map(str, b.inputs), *(f'{q} {n} 0' for q, n in zip(b.q, b.next)),
             *map(str, constraints), '1', str(justice), *map(str, fair),
             *(' '.join(map(str, g)) for g in b.gates)]
    return '\n'.join(lines) + '\n'


def safety_reachable(text):
    # Independent truth-table evaluator for generated pure safety AAGs.
    lines = iter(text.splitlines())
    _, _, ni, nl, no, na, nb, nc, nj, nf = next(lines).split()
    ni, nl, na, nc = map(int, (ni, nl, na, nc))
    assert (no, nb, nj, nf) == ('0', '1', '0', '0')
    inputs = [int(next(lines)) for _ in range(ni)]
    latches = [list(map(int, next(lines).split())) for _ in range(nl)]
    bad = int(next(lines))
    constraints = [int(next(lines)) for _ in range(nc)]
    gates = [list(map(int, next(lines).split())) for _ in range(na)]
    initial = list(product(*[(0, 1) if init == q else (init,) for q, _, init in latches]))
    seen, pending = set(initial), deque(initial)
    while pending:
        state = pending.popleft()
        for choice in product((0, 1), repeat=ni):
            values = {0: 0, **dict(zip(inputs, choice)), **{row[0]: value for row, value in zip(latches, state)}}
            def value(lit):
                return values[lit & ~1] ^ (lit & 1)
            for lhs, a, b in gates:
                values[lhs] = value(a) & value(b)
            if not all(value(c) for c in constraints):
                continue
            if value(bad):
                return True
            nxt = tuple(value(n) for _, n, _ in latches)
            if nxt not in seen:
                seen.add(nxt)
                pending.append(nxt)
    return False


def test_exact_lasso_and_sufficient_k_liveness():
    for kind, accepting in [('toggle', False), ('stuck', True)]:
        model = read(progress_model(kind))
        assert safety_reachable(reduce(model)[0]) is accepting
        assert safety_reachable(reduce(model, 'k-live', 2)[0]) is accepting
    # A finite accepting prefix is not an infinite accepting execution.
    model = read(progress_model('toggle'))
    assert safety_reachable(reduce(model, 'k-live', 1)[0])
    assert not safety_reachable(reduce(model)[0])


def test_fairness_changes_answer_and_is_not_an_invariant_assumption():
    unfair = read(progress_model('input'))
    fair = read(progress_model('input', 'ready'))
    assert safety_reachable(reduce(unfair)[0])
    assert not safety_reachable(reduce(fair)[0])
    assert safety_reachable(reduce(fair, feasibility=True)[0])
    infeasible = read(progress_model('input', 'false'))
    assert not safety_reachable(reduce(infeasible, feasibility=True)[0])
    constrained = read(progress_model('input', constraint='false'))
    assert not safety_reachable(reduce(constrained, feasibility=True)[0])


def test_aiger_layout_and_strict_property_inventory():
    model = read('aag 2 1 0 0 1 0 1 1 1\n2\n1\n2\n4\n2\n2\n4 2 2\ni0 x\nj0 bad\nc\ncomment\n')
    assert model.constraints == [1] and model.justice == [4, 2] and model.fairness == [2]
    with pytest.raises(ValueError, match='one justice'):
        read('aag 0 0 0 1 0 0 0 1\n0\n1\n0\n')
    with pytest.raises(ValueError, match='one justice'):
        read('aag 0 0 0 0 0 0 0 2\n1\n1\n0\n0\n')
    with pytest.raises(ValueError, match='undefined'):
        read('aag 1 0 0 0 0 0 0 1\n1\n2\n')
    with pytest.raises(ValueError, match='footer'):
        read('aag 0 0 0 0 0 0 0 1\n1\n1\n45\n')


def test_unknown_initial_state_and_combinational_justice():
    model = read('aag 1 0 1 0 0 0 0 1\n2 2 2\n1\n2\n')
    assert safety_reachable(reduce(model)[0])
    model = read('aag 1 1 0 0 0 0 0 1\n2\n1\n2\n')
    assert safety_reachable(reduce(model)[0])


def test_lasso_matches_all_one_bit_deterministic_models():
    # Independent oracle: follow the source transition until its first repeat.
    # Goals must each hold somewhere in that recurrent cycle, not at one time.
    for nxt, justice, fairness in product((0, 1, 2, 3), repeat=3):
        text = f'aag 1 0 1 0 0 0 0 1 1\n2 {nxt} 0\n1\n{justice}\n{fairness}\n'
        def evaluate(lit, state):
            return (state if lit >= 2 else 0) ^ (lit & 1)
        visited, state = [], 0
        while state not in visited:
            visited.append(state)
            state = evaluate(nxt, state)
        cycle = visited[visited.index(state):]
        accepting = all(any(evaluate(goal, q) for q in cycle) for goal in (justice, fairness))
        assert safety_reachable(reduce(read(text))[0]) is accepting, text
        # An unreachable finite round count can only occur on a rejecting model.
        if not safety_reachable(reduce(read(text), 'k-live', 4)[0]):
            assert not accepting, text
    model = read('aag 1 0 1 0 0 0 0 1\n2 3 0\n2\n2\n3\n')
    assert safety_reachable(reduce(model)[0])  # GF q and GF !q both hold.


def test_k_bound_validation():
    with pytest.raises(ValueError, match='k must'):
        reduce(read(progress_model()), 'k-live', 0)
