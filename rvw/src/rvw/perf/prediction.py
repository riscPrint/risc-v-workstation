"""Observed predictor outcomes. No predictor model or project signal bindings."""
from collections import defaultdict
import re


def parse(fields, cycle, instructions, seen):
    if len(fields) != 13:
        raise ValueError('prediction requires ten event fields')
    _, _, _, key, predictor, kind, predicted, actual, recovery, work, warmup, alias, context = fields
    if instructions[key].end is not None:
        raise ValueError('prediction after terminal R')
    if not predictor or predictor == '?' or not context:
        raise ValueError('missing predictor or context token')
    if kind == 'direction':
        if predicted not in ('taken', 'not_taken') or actual not in ('taken', 'not_taken'):
            raise ValueError('invalid direction')
    elif kind in ('target', 'return'):
        def address(value):
            if not re.fullmatch(r'(0x[0-9a-fA-F]+|[0-9]+)', value):
                raise ValueError('invalid prediction address')
            return int(value, 16 if value.startswith('0x') else 10)
        predicted, actual = address(predicted), address(actual)
    else:
        raise ValueError('invalid prediction kind')
    identity = key, predictor, kind
    if identity in seen:
        raise ValueError('duplicate prediction outcome')
    seen.add(identity)
    def count(value):
        if value == '?':
            return None
        if not value.isascii() or not value.isdecimal():
            raise ValueError('invalid observed count')
        return int(value)
    if warmup not in ('true', 'false', '?') or alias not in ('true', 'false', '?'):
        raise ValueError('invalid warmup or alias state')
    return dict(cycle=cycle, instruction=key, predictor=predictor, kind=kind,
                correct=predicted == actual, recovery_cycles=count(recovery),
                wrong_path_instructions=count(work), warmup=warmup, alias=alias, context=context)


def report(events):
    groups = defaultdict(list)
    for event in events:
        groups[tuple(event[k] for k in ('predictor', 'kind', 'warmup', 'alias', 'context'))].append(event)
    rows = []
    for key, values in sorted(groups.items()):
        row = dict(zip(('predictor', 'kind', 'warmup', 'alias', 'context'), key))
        row.update(outcomes=len(values), correct=sum(v['correct'] for v in values))
        row['incorrect'] = row['outcomes'] - row['correct']
        for metric in ('recovery_cycles', 'wrong_path_instructions'):
            observed = [v[metric] for v in values if v[metric] is not None]
            row[metric] = dict(samples=len(observed), unknown=len(values) - len(observed),
                               sum=sum(observed) if observed else None,
                               max=max(observed) if observed else None)
        rows.append(row)
    return dict(outcomes=len(events), by_context=rows,
                basis='Explicit producer observations only. ? means unknown. Context and alias groups do not prove causation. Recovery and work can overlap across kinds; do not sum groups as global cost.')
