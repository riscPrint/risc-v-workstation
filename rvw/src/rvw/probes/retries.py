"""Instruction-linked retry observations. These observations never drive a prediction."""
from collections import Counter, defaultdict


def retry_statistics(stream):
    """Track dynamic lifetimes, including ROB wrap and tail flushes.

    Retry-to-completion is an observed span, not an isolated causal penalty.
    Only a later Wb stage closes a span. Retirement alone is not completion.
    """
    live = {}
    counts = Counter()
    spans = defaultdict(list)
    findings = []
    sequence = 0
    first = any(p.meta.get('first') == 'true' for p in stream.of_kind('stage'))

    def close(i, outcome):
        entry = live.pop(i)
        for cause, cycle in entry['pending']:
            counts[cause, outcome] += 1

    for cycle, p, v in stream.events('stage', 'lsuretry', 'retire', 'flush'):
        i = v['id']
        if p.kind == 'stage':
            starts = p.meta.get('first') == 'true' if first else i not in live
            if starts:
                if i in live:
                    close(i, 'reused')
                live[i] = dict(sequence=sequence, pending=[])
                sequence += 1
            if i in live and p.meta.get('stage') == 'Wb':
                for cause, start in live[i]['pending']:
                    if cause != 'memory_order_violation':
                        spans[cause].append(cycle-start)
                # A stale completion can follow detection before the tail flush.
                live[i]['pending'] = [(cause, start) for cause, start in live[i]['pending']
                                      if cause == 'memory_order_violation']
        elif p.kind == 'lsuretry':
            cause = p.meta['cause']
            counts[cause, 'attempts'] += 1
            if i not in live:
                findings.append(dict(cycle=cycle, id=i, cause=cause, message='retry has no live first-stage ID'))
                counts[cause, 'orphan'] += 1
            else:
                # A second rejected attempt ends the earlier attempt's wait span.
                for previous, start in live[i]['pending']:
                    counts[previous, 'rejected_again' if previous == cause else 'superseded'] += 1
                live[i]['pending'] = [(cause, cycle)]
                counts[cause, 'linked'] += 1
        elif p.kind == 'retire':
            if i in live:
                close(i, 'retired_without_completion')
        elif i in live:
            anchor = live[i]['sequence']
            victims = [j for j, e in live.items() if
                       (e['sequence'] > anchor or (j == i and v.get('inclusive'))) ] if p.meta.get('range') == 'younger' else [i]
            for j in victims:
                close(j, 'flushed')
    for i in list(live):
        close(i, 'censored')
    causes = sorted({p.meta['cause'] for p in stream.of_kind('lsuretry')})
    return dict(schema='rvw.lsu-retry-statistics/1',
                status='violations' if findings else ('observed' if stream.end else 'inconclusive'),
                causes={c: dict(counts={k: n for (cause, k), n in counts.items() if cause == c},
                                retry_to_completion_cycles=spans[c]) for c in causes},
                findings=findings,
                limits=['completion spans include service and queue waits; they are not isolated recovery costs',
                        'flushed, repeated and incomplete attempts do not supply a completion span'])
