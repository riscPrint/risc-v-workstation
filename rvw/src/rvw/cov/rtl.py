"""Typed, instance-scoped RTL samples. No ISA decoder or core names."""
import json
from hashlib import sha256

from . import captured


def identity(plan):
    return sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def exact_keys(obj, required, optional=()):
    if not isinstance(obj, dict) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        raise ValueError(f'expected fields {required}, optional {optional}')


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'expected integer in {low}..{high}')


def validate(plan):
    exact_keys(plan, ('schema', 'design', 'clock', 'reset', 'signals', 'bins'), ('sequences',))
    if plan['schema'] != 'rvw.rtl-plan/1' or not isinstance(plan['design'], str) or not plan['design']:
        raise ValueError('expected rvw.rtl-plan/1 with a design identity')
    exact_keys(plan['clock'], ('signal', 'edge', 'sampling'))
    if plan['clock']['edge'] != 'rising' or plan['clock']['sampling'] != 'pre-edge':
        raise ValueError('only rising-edge pre-edge sampling is supported')
    exact_keys(plan['reset'], ('signal', 'active', 'rule'))
    integer(plan['reset']['active'], 0, 1)
    if plan['reset']['rule'] != 'disable-clear':
        raise ValueError('only disable-clear reset is supported')
    signals = plan['signals']
    if not isinstance(signals, dict) or not signals:
        raise ValueError('signals must be a nonempty object')
    for name, signal in signals.items():
        if not name or '*' in name:
            raise ValueError('signal paths must name exact instances')
        exact_keys(signal, ('width', 'type', 'scala'))
        integer(signal['width'], 1, 4096)
        if not isinstance(signal['type'], str) or not signal['type']:
            raise ValueError('signal type is required')
        if signal['scala'] is not None:
            exact_keys(signal['scala'], ('file', 'line'))
            integer(signal['scala']['line'], 1, 2**31 - 1)
    for control in (plan['clock']['signal'], plan['reset']['signal']):
        if control not in signals or signals[control]['width'] != 1:
            raise ValueError('clock and reset must be declared one-bit signals')

    def predicate(pred):
        if not isinstance(pred, dict) or not pred:
            raise ValueError('predicate must contain signal domains')
        for signal, domain in pred.items():
            if signal not in signals or not isinstance(domain, list) or not domain:
                raise ValueError('predicate needs a declared signal and nonempty value list')
            for value in domain:
                integer(value, 0, 2**signals[signal]['width'] - 1)
    ids = set()
    for item in plan['bins']:
        exact_keys(item, ('id', 'kind', 'domain', 'when'), ('from',))
        if item['kind'] not in ('event', 'occupancy', 'state', 'transition', 'arbitration'):
            raise ValueError('unsupported bin kind')
        if item['domain'] not in ('committed', 'speculative', 'structural'):
            raise ValueError('unsupported event domain')
        predicate(item['when'])
        if item['kind'] == 'transition':
            predicate(item.get('from'))
        elif 'from' in item:
            raise ValueError('from is supported only for transition bins')
        if not isinstance(item['id'], str) or not item['id'] or item['id'] in ids:
            raise ValueError('bin IDs must be nonempty and unique')
        ids.add(item['id'])
    for seq in plan.get('sequences', []):
        exact_keys(seq, ('id', 'domain', 'steps'))
        if not isinstance(seq['id'], str) or not seq['id'] or seq['id'] in ids:
            raise ValueError('sequence IDs must be nonempty and unique')
        ids.add(seq['id'])
        if seq['domain'] not in ('committed', 'speculative', 'structural') or not 2 <= len(seq['steps']) <= 32:
            raise ValueError('sequence needs a domain and 2..32 steps')
        for i, step in enumerate(seq['steps']):
            exact_keys(step, ('when',) if i == 0 else ('when', 'delay'))
            predicate(step['when'])
            if i:
                if not isinstance(step['delay'], list) or len(step['delay']) != 2:
                    raise ValueError('delay must be [minimum, maximum]')
                lo, hi = step['delay']
                integer(lo, 1, 1000000)
                integer(hi, lo, 1000000)


def matches(predicate, values):
    return all(values[signal] in domain for signal, domain in predicate.items())


@captured.command
def sample(plan_path, traces):
    plan = json.loads(captured.read_text(plan_path))
    validate(plan)
    plan_id = identity(plan)
    counts = {b['id']: 0 for b in plan['bins']}
    sequences = {s['id']: dict(activated=0, completed=0, expired=0, reset_cancelled=0, pending=0)
                 for s in plan.get('sequences', [])}
    inputs, complete = [], True
    seen = set()
    for path in traces:
        item = captured.file(path)
        if item.sha256 in seen:
            raise ValueError('duplicate RTL sample trace')
        seen.add(item.sha256)
        inputs.append({'path': item.resolved, 'sha256': item.sha256})
        with item.copy.open() as stream:
            header = json.loads(next(stream))
            exact_keys(header, ('schema', 'plan_id', 'design'))
            if header != {'schema': 'rvw.rtl-samples/1', 'plan_id': plan_id, 'design': plan['design']}:
                raise ValueError('RTL trace identity differs from plan')
            previous, last, ended = None, None, False
            active = {s['id']: [] for s in plan.get('sequences', [])}
            for line in stream:
                row = json.loads(line)
                if ended:
                    raise ValueError('records after RTL trace end')
                if row.get('event') == 'end':
                    exact_keys(row, ('event', 'complete'))
                    if type(row['complete']) is not bool:
                        raise ValueError('complete must be boolean')
                    complete &= row['complete']
                    ended = True
                    continue
                exact_keys(row, ('cycle', 'values'))
                cycle, values = row['cycle'], row['values']
                integer(cycle, 0, 2**63 - 1)
                if last is not None and cycle != last + 1:
                    raise ValueError('RTL samples must have consecutive cycles')
                last = cycle
                if not isinstance(values, dict) or values.keys() != plan['signals'].keys():
                    raise ValueError('sample must contain every declared signal exactly once')
                for name, value in values.items():
                    integer(value, 0, 2**plan['signals'][name]['width'] - 1)
                if values[plan['clock']['signal']] != 0:
                    raise ValueError('pre-edge clock must be low')
                if values[plan['reset']['signal']] == plan['reset']['active']:
                    previous = None
                    for name, attempts in active.items():
                        sequences[name]['reset_cancelled'] += len(attempts)
                        attempts.clear()
                    continue
                for b in plan['bins']:
                    if matches(b['when'], values) and (b['kind'] != 'transition' or
                            previous is not None and matches(b['from'], previous)):
                        counts[b['id']] += 1
                for seq in plan.get('sequences', []):
                    stats = sequences[seq['id']]
                    keep = []
                    for index, since in active[seq['id']]:
                        step = seq['steps'][index]
                        age = cycle - since
                        lo, hi = step['delay']
                        if age > hi:
                            stats['expired'] += 1
                        elif age >= lo and matches(step['when'], values):
                            # Deterministic first-match advancement; one completion per activation.
                            if index + 1 == len(seq['steps']):
                                stats['completed'] += 1
                            else:
                                keep.append((index + 1, cycle))
                        else:
                            keep.append((index, since))
                    if matches(seq['steps'][0]['when'], values):
                        stats['activated'] += 1
                        keep.append((1, cycle))
                    active[seq['id']] = keep
                previous = values
            if not ended or last is None:
                complete = False
            for name, attempts in active.items():
                sequences[name]['pending'] += len(attempts)
    if not inputs:
        raise ValueError('at least one trace is required')
    return {'schema': 'rvw.rtl-coverage/1', 'plan_id': plan_id, 'design': plan['design'],
            'status': 'ok' if complete else 'inconclusive', 'inputs': inputs,
            'sampling_complete': complete, 'bins': [dict(b, count=counts[b['id']],
                observation='observed' if counts[b['id']] else 'unobserved',
                reachability='undetermined') for b in plan['bins']],
            'sequences': [dict(s, **sequences[s['id']]) for s in plan.get('sequences', [])],
            'denominator': len(counts), 'observed_bins': sum(v > 0 for v in counts.values()),
            'proven_unreachable_bins': 0}
