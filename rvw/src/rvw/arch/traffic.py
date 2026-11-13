"""Project-owned multi-agent traffic through finite pipelined resources."""
import heapq
import json
import math
from pathlib import Path


def positive(value, name, zero=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError(f'{name} must be finite and positive')
    return value


def model(spec):
    if spec.get('schema') != 'rvw.traffic-plan/1':
        raise ValueError('expected rvw.traffic-plan/1')
    resources = spec['resources']
    if not isinstance(resources, dict) or not resources:
        raise ValueError('resources must be nonempty')
    state = {}
    for name, config in resources.items():
        for field in ('bytes_per_cycle', 'latency', 'capacity'):
            positive(config[field], field, zero=field == 'latency')
        if type(config['capacity']) is not int or type(config['latency']) is not int:
            raise ValueError('capacity and latency must be integers')
        if 'power' in config:
            power = config['power']
            for key in ('active_w', 'idle_w', 'sleep_w', 'sleep_after', 'wake_cycles', 'wake_j'):
                positive(power[key], key, zero=True)
            if any(type(power[k]) is not int for k in ('sleep_after', 'wake_cycles')):
                raise ValueError('power state delays must be integer cycles')
            if not isinstance(power.get('source'), str) or not power['source'].strip():
                raise ValueError('power model needs a source')
            positive(spec.get('clock_hz'), 'clock_hz')
        state[name] = dict(ready=0, flights=[], bytes=0, transactions=0, peak=0,
                           queue_wait_cycles=0, queue_full=0, busy_cycles=0,
                           intervals=[], wakes=0, last_finish=0)
    events = []
    seq = 0
    requests = {}
    agents = spec['agents']
    if not isinstance(agents, dict) or not agents:
        raise ValueError('agents must be nonempty')
    for agent, data in agents.items():
        route = data['route']
        if not isinstance(route, list) or not route or any(r not in resources for r in route):
            raise ValueError('agent route must name resources')
        if len(set(route)) != len(route):
            raise ValueError('cyclic resource routes are unsupported')
        for request in data['requests']:
            arrival, size = request['cycle'], request['bytes']
            positive(arrival, 'cycle', zero=True); positive(size, 'bytes')
            if type(arrival) is not int or type(size) is not int:
                raise ValueError('request cycle and bytes must be integers')
            requests[seq] = dict(agent=agent, route=route, bytes=size, start=arrival)
            heapq.heappush(events, (arrival, seq, 0, arrival))
            seq += 1
    if not requests:
        raise ValueError('requests must be nonempty')
    completed = []
    # Each event carries the first arrival at this resource so retry waiting
    # contributes once. Request ID breaks simultaneous-arrival ties.
    while events:
        cycle, ident, hop, arrived = heapq.heappop(events)
        request = requests[ident]
        name = request['route'][hop]
        c, s = resources[name], state[name]
        while s['flights'] and s['flights'][0] <= cycle:
            heapq.heappop(s['flights'])
        if len(s['flights']) >= c['capacity']:
            s['queue_full'] += 1
            heapq.heappush(events, (s['flights'][0], ident, hop, arrived))
            continue
        start = max(cycle, s['ready'])
        power = c.get('power')
        if power and start - s['last_finish'] > power['sleep_after']:
            start += power['wake_cycles']
            s['wakes'] += 1
        transfer = math.ceil(request['bytes'] / c['bytes_per_cycle'])
        finish = start + transfer + c['latency']
        s['ready'] = start + transfer
        s['last_finish'] = max(s['last_finish'], finish)
        heapq.heappush(s['flights'], finish)
        s['peak'] = max(s['peak'], len(s['flights']))
        s['queue_wait_cycles'] += start - arrived
        s['bytes'] += request['bytes']; s['transactions'] += 1
        s['busy_cycles'] += transfer
        s['intervals'].append((start, finish))
        if hop + 1 < len(request['route']):
            heapq.heappush(events, (finish, ident, hop + 1, finish))
        else:
            completed.append(dict(id=ident, agent=request['agent'], bytes=request['bytes'],
                                  start=request['start'], finish=finish, latency=finish-request['start']))
    horizon = max(row['finish'] for row in completed)
    rows = {}
    for name, s in state.items():
        config = resources[name]
        # Union of overlapping service intervals defines resource activity.
        merged = []
        for start, finish in sorted(s.pop('intervals')):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], finish)
            else:
                merged.append([start, finish])
        active = sum(b-a for a, b in merged)
        energy = None
        power = config.get('power')
        sleep = 0
        if power:
            previous = 0
            for start, finish in merged + [[horizon, horizon]]:
                sleep += max(0, start - previous - power['sleep_after'])
                previous = finish
            idle = max(0, horizon-active-sleep)
            energy = (active * power['active_w'] + idle * power['idle_w'] + sleep * power['sleep_w']) / spec['clock_hz'] + s['wakes']*power['wake_j']
        rows[name] = {k: v for k, v in s.items() if k not in ('flights', 'ready', 'last_finish')}
        rows[name].update(active_cycles=active, sleep_cycles=sleep if power else None,
                          bandwidth_bytes_per_cycle=s['bytes']/horizon, utilization=s['busy_cycles']/horizon,
                          energy_j=energy, power_source=power.get('source') if power else None)
    by_agent = {}
    for agent in agents:
        values = [row for row in completed if row['agent'] == agent]
        by_agent[agent] = dict(requests=len(values), bytes=sum(r['bytes'] for r in values),
                              mean_latency=sum(r['latency'] for r in values)/len(values) if values else None)
    return dict(schema='rvw.traffic-report/1', status='reported', evidence='model-only', cycles=horizon,
                resources=rows, agents=by_agent, requests=sorted(completed, key=lambda r: r['id']),
                accuracy_status='inconclusive', limits=['declared post-cache traffic', 'no coherence or cache replacement',
                'store-and-forward routes; upstream release precedes downstream admission',
                'abstract project power parameters; no cell-level power or RTL calibration'])


def traffic(plan, out, project=None):
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    spec = json.loads(Path(plan).read_text())
    result = model(spec)
    with Path(out).open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result
