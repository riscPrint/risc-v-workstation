"""Finite whole-message TileLink-C permission abstraction, not a channel model."""
from collections import deque
from dataclasses import dataclass, replace
import argparse
import json
from pathlib import Path


@dataclass(frozen=True)
class State:
    permission: tuple = (0, 0)  # N, B, T
    data: tuple = (0, 0)
    life: tuple = (0, 0)  # not issued, queued, done
    want: tuple = (0, 0)
    memory: int = 0
    latest: int = 0
    active: int = -1
    phase: str = 'idle'


def put(values, i, value):
    return values[:i] + (value,) + values[i + 1:]


def successors(s, bug=None):
    for i in range(2):
        if s.life[i] == 0:
            for p in (1, 2):
                yield f'A.acquire.{i}.{p}', replace(s, life=put(s.life, i, 1), want=put(s.want, i, p))
        if s.life[i] == 2 and s.permission[i]:
            memory = s.data[i] if s.permission[i] == 2 else s.memory
            yield f'C.release.{i}', replace(s, permission=put(s.permission, i, 0), memory=memory)
    if s.phase == 'idle':
        for i in range(2):
            if s.life[i] == 1:
                yield f'home.select.{i}', replace(s, active=i, phase='probe')
    else:
        i = s.active
        j = 1 - i
        if s.phase == 'probe':
            conflict = s.permission[j] == 2 or (s.want[i] == 2 and s.permission[j] != 0)
            phase = 'ack' if conflict and bug != 'grant_conflict' else 'grant'
            yield f'B.probe.{j}' if conflict else 'home.no_probe', replace(s, phase=phase)
        elif s.phase == 'ack' and bug != 'lost_ack':
            memory = s.memory if bug == 'stale_data' or s.permission[j] != 2 else s.data[j]
            perm = 0 if s.want[i] == 2 else min(s.permission[j], 1)
            yield f'C.probe_ack.{j}', replace(s, permission=put(s.permission, j, perm), memory=memory, phase='grant')
        elif s.phase == 'grant':
            yield f'D.grant.{i}', replace(s, permission=put(s.permission, i, s.want[i]), data=put(s.data, i, s.memory), phase='finish')
        elif s.phase == 'finish':
            value = 1 - s.latest if s.permission[i] == 2 else s.latest
            yield f'E.grant_ack.{i}', replace(s, data=put(s.data, i, value), latest=value, life=put(s.life, i, 2), active=-1, phase='idle')
        if bug == 'retry' and s.phase == 'ack':
            yield 'home.retry', replace(s, phase='probe')


def invariant(s):
    if any(p == 2 and s.permission[1-i] != 0 for i, p in enumerate(s.permission)):
        return 'swmr'
    if any(p and s.data[i] != s.latest for i, p in enumerate(s.permission)):
        return 'data_value'
    if 2 not in s.permission and s.memory != s.latest:
        return 'home_data'
    return None


def terminal(s):
    return s.life == (2, 2) and s.phase == 'idle'


def explore(bug=None, limit=100000):
    if limit < 1:
        raise ValueError('state limit must be positive')
    root = State()
    parent = {root: None}
    graph = {}
    queue = deque([root])

    def witness(s):
        path = []
        while parent[s] is not None:
            before, action = parent[s]
            path.append(action)
            s = before
        return list(reversed(path))

    def report(verdict, failure=None, path=None):
        return {'schema': 'rvw.coherence-model/1', 'verdict': verdict,
                'failure': failure, 'states': len(parent),
                'edges': sum(map(len, graph.values())), 'witness': path or [],
                'scope': {'agents': 2, 'homes': 1, 'lines': 1, 'values': 2,
                          'requests_per_agent': 1, 'whole_message': True,
                          'progress': 'nonterminal cycle exclusion; environment stutter omitted'}}

    while queue:
        s = queue.popleft()
        failure = invariant(s)
        if failure:
            return report('fail', failure, witness(s)), graph
        edges = list(successors(s, bug))
        graph[s] = edges
        if not edges and not terminal(s):
            return report('fail', 'deadlock', witness(s)), graph
        for action, nxt in edges:
            if nxt not in parent:
                if len(parent) >= limit:
                    return report('inconclusive', 'state_limit'), graph
                parent[nxt] = (s, action)
                queue.append(nxt)
    # Iterative DFS detects any nonterminal cycle, including a retry with an exit.
    # This stronger-than-fair-liveness check is valid only for this finite workload.
    color = {}
    for start in graph:
        if terminal(start) or start in color:
            continue
        color[start] = 1
        stack = [(start, iter(graph[start]))]
        trace = []
        while stack:
            s, edges = stack[-1]
            edge = next(edges, None)
            if edge is None:
                color[s] = 2
                stack.pop()
                if trace:
                    trace.pop()
                continue
            action, nxt = edge
            if terminal(nxt):
                continue
            if color.get(nxt) == 1:
                return report('fail', 'livelock_cycle', witness(start) + trace + [action]), graph
            if nxt not in color:
                color[nxt] = 1
                trace.append(action)
                stack.append((nxt, iter(graph[nxt])))
    return report('pass'), graph


def relation(graph):
    """Finite-path projection allows several abstract steps per RTL sample.

    Data, channel phase and request history are hidden. This relation checks
    permission safety only. It cannot prove a channel implementation refines TL-C.
    """
    states = {s.permission for s in graph}
    edges = {(s.permission, n.permission) for s, es in graph.items() for _, n in es}
    edges |= {(s, s) for s in states}
    while True:
        extended = edges | {(a, d) for a, b in edges for c, d in edges if b == c}
        if extended == edges:
            return states, edges
        edges = extended


def generate(graph):
    states, edges = relation(graph)
    encode = lambda p: p[0] + 3*p[1]
    pairs = ', '.join(f'({encode(a)}, {encode(b)})' for a, b in sorted(edges))
    legal = ', '.join(str(encode(p)) for p in sorted(states))
    return f'''// Generated by SpinalChecks/coherence/model.py. Do not edit.
package spinalchecks.coherence

object PermissionRelation {{
  val states: Set[Int] = Set({legal})
  val edges: Set[(Int, Int)] = Set({pairs})
  def encode(a: Int, b: Int): Int = {{
    require(a >= 0 && a <= 2 && b >= 0 && b <= 2, "invalid permission")
    a + 3*b
  }}
  def check(before: Int, after: Int): Unit =
    require(states(after) && edges((before, after)), "coherence permission transition")
}}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bug', choices=['grant_conflict', 'stale_data', 'lost_ack', 'retry'])
    parser.add_argument('--limit', type=int, default=100000)
    parser.add_argument('--generate', type=Path)
    parser.add_argument('--fair', action='store_true', help='check finite request completion under named weak fairness')
    args = parser.parse_args()
    if args.fair:
        if args.generate:
            parser.error('--fair cannot generate the permission projection')
        import fair
        assumptions = {'internal_no_probe': {'home.no_probe'}}
        for i in range(2):
            assumptions[f'environment_issue_{i}'] = {f'A.acquire.{i}.1', f'A.acquire.{i}.2'}
            for action in ('home.select', 'B.probe', 'C.probe_ack', 'D.grant', 'E.grant_ack'):
                assumptions[f'{action}.{i}'] = {f'{action}.{i}'}
        result = fair.explore(State(), lambda s: successors(s, args.bug), invariant, terminal,
                              {f'hart-{i}': lambda s, i=i: s.life[i] != 2 for i in range(2)},
                              assumptions, args.limit)
        print(json.dumps(result, indent=2))
        return {'pass': 0, 'fail': 1, 'inconclusive': 3}[result['status']]
    result, graph = explore(args.bug, args.limit)
    if args.generate:
        if args.bug or result['verdict'] != 'pass':
            parser.error('generate only from an exhausted unmutated model')
        args.generate.write_text(generate(graph))
    print(json.dumps(result, indent=2))
    return {'pass': 0, 'fail': 1, 'inconclusive': 3}[result['verdict']]


if __name__ == '__main__':
    raise SystemExit(main())
