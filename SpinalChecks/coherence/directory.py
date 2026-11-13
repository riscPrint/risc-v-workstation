"""Finite two-client queued MESI/MOESI directory abstraction.

One home serializes each line independently. Channels carry whole single-beat
messages. This is a model experiment, not a complete TileLink implementation.
"""
from dataclasses import dataclass, replace
import argparse
import json
from fair import explore

I, S, E, M, O = range(5)


def put(values, index, value):
    return values[:index] + (value,) + values[index+1:]


@dataclass(frozen=True)
class State:
    permission: tuple
    data: tuple
    memory: tuple
    latest: tuple
    issued: tuple = (0, 0)
    done: tuple = (0, 0)
    active: tuple = ()
    a: tuple = ()
    b: tuple = ()
    c: tuple = ()
    d: tuple = ()
    e: tuple = ()


def initial(lines):
    return State((I,)*(2*lines), (0,)*(2*lines), (0,)*lines, (0,)*lines, active=((),)*lines)


def successors(s, lines=1, requests=1, profile='mesi', bug=None):
    for client in range(2):
        if s.issued[client] != s.done[client] or s.done[client] >= requests:
            continue
        for line in range(lines):
            index = client*lines+line
            permission = s.permission[index]
            for write in (0, 1):
                if (not write and permission != I) or (write and permission in (E, M)):
                    value = 1-s.latest[line] if write else s.latest[line]
                    yield f'local.{client}', replace(s,
                        permission=put(s.permission, index, M if write else permission),
                        data=put(s.data, index, value), latest=put(s.latest, line, value),
                        issued=put(s.issued, client, s.issued[client]+1), done=put(s.done, client, s.done[client]+1))
                elif not s.a:
                    yield f'issue.{client}', replace(s, a=(client, line, write), issued=put(s.issued, client, s.issued[client]+1))
    if s.a:
        client, line, write = s.a
        if not s.active[line] and not (bug == 'starvation' and client == 0):
            # client, write, phase, probed-mask, forwarded-data, forward-valid
            tx = (client, write, 0, 0, 0, False)
            yield f'home.take.{client}', replace(s, a=(), active=put(s.active, line, tx))
    for line, tx in enumerate(s.active):
        if not tx:
            continue
        client, write, phase, probed, forwarded, valid = tx
        peer = 1-client
        permission = s.permission[peer*lines+line]
        conflict = permission != I if write else permission in (E, M, O)
        if phase == 0:
            if conflict and not (probed & (1 << peer)) and bug != 'early_grant':
                if not s.b:
                    yield f'home.probe.{client}', replace(s, b=(peer, line, write),
                        active=put(s.active, line, (client, write, 1, probed, forwarded, valid)))
            elif not s.d:
                mine = client*lines+line
                value = s.data[mine] if s.permission[mine] != I else forwarded if valid else s.memory[line]
                cap = M if write else E if permission == I else S
                yield f'home.grant.{client}', replace(s, d=(client, line, cap, value, write),
                    active=put(s.active, line, (client, write, 2, probed, forwarded, valid)))
    if s.b and not s.c:
        peer, line, write = s.b
        index = peer*lines+line
        old = s.permission[index]
        cap = I if write else O if profile == 'moesi' and old in (M, O) else S
        value = s.data[index]
        if bug == 'stale_data':
            value = 1-value
        yield f'client.probe_ack.{peer}', replace(s, b=(), c=(peer, line, value), permission=put(s.permission, index, cap))
    if s.c:
        peer, line, value = s.c
        tx = s.active[line]
        if tx:
            client, write, phase, probed, _, _ = tx
            if phase == 1 and not (bug == 'lost_ack' and peer == 0) and not (bug == 'cyclic_wait' and not s.d):
                dirty_owner_retained = profile == 'moesi' and not write and s.permission[peer*lines+line] == O
                memory = s.memory if dirty_owner_retained else put(s.memory, line, value)
                yield f'home.probe_ack.{peer}', replace(s, c=(), memory=memory,
                    active=put(s.active, line, (client, write, 0, probed | (1 << peer), value, True)))
    if s.d and not s.e:
        client, line, permission, value, write = s.d
        if write:
            value = 1-s.latest[line]
        index = client*lines+line
        yield f'client.grant.{client}', replace(s, d=(), e=(client, line),
            permission=put(s.permission, index, permission), data=put(s.data, index, value),
            latest=put(s.latest, line, value) if write else s.latest)
    if s.e:
        client, line = s.e
        yield f'home.grant_ack.{client}', replace(s, e=(), active=put(s.active, line, ()),
            done=put(s.done, client, s.done[client]+1))


def invariant(s, lines, profile):
    for line in range(lines):
        ps = [s.permission[c*lines+line] for c in range(2)]
        if any(p in (E, M) and ps[1-c] != I for c, p in enumerate(ps)):
            return 'exclusive_permission'
        if ps.count(O) > 1 or (O in ps and any(p not in (I, S, O) for p in ps)) or (profile == 'mesi' and O in ps):
            return 'dirty_ownership'
        if any(p != I and s.data[c*lines+line] != s.latest[line] for c, p in enumerate(ps)):
            return 'cache_data'
        if s.c and s.c[1] == line and s.c[2] != s.latest[line]:
            return 'intervention_data'
        if not any(p in (M, O) for p in ps) and s.memory[line] != s.latest[line]:
            tx = s.active[line]
            buffered = (s.c and s.c[1] == line and s.c[2] == s.latest[line]) or (tx and tx[5] and tx[4] == s.latest[line])
            if not buffered:
                return 'home_data'
    return None


def run(profile='mesi', lines=1, requests=1, bug=None, limit=100000):
    if profile not in ('mesi', 'moesi') or not 1 <= lines <= 2 or not 1 <= requests <= 3:
        raise ValueError('supported bounds: MESI/MOESI, 1..2 lines, 1..3 requests per client')
    fairness = {}
    for client in range(2):
        fairness[f'program.{client}'] = {f'issue.{client}', f'local.{client}'}
        for action in ('home.take', 'home.probe', 'client.probe_ack', 'home.probe_ack', 'home.grant', 'client.grant', 'home.grant_ack'):
            fairness[f'{action}.{client}'] = {f'{action}.{client}'}
    complete = lambda s: s.done == (requests, requests) and not any(s.active) and not any((s.a, s.b, s.c, s.d, s.e))
    report = explore(initial(lines), lambda s: successors(s, lines, requests, profile, bug),
                     lambda s: invariant(s, lines, profile), complete,
                     {f'client-{c}': lambda s, c=c: s.done[c] < requests for c in range(2)}, fairness, limit)
    return report | {'profile': profile, 'bounds': {'clients': 2, 'homes': 1, 'lines': lines,
                    'requests_per_client': requests, 'queue_capacity_per_channel': 1,
                    'values': 2, 'whole_message': True}, 'independent_model_crosscheck': 'not_run'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', choices=('mesi', 'moesi'), default='mesi')
    p.add_argument('--lines', type=int, default=1)
    p.add_argument('--requests', type=int, default=1)
    p.add_argument('--limit', type=int, default=100000)
    p.add_argument('--bug', choices=('lost_ack', 'stale_data', 'early_grant', 'starvation', 'cyclic_wait'))
    args = p.parse_args()
    report = run(args.profile, args.lines, args.requests, args.bug, args.limit)
    print(json.dumps(report, indent=2))
    return {'pass': 0, 'fail': 1, 'inconclusive': 3}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
