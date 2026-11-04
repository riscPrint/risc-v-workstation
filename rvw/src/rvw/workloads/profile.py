"""Whole-program instruction categories from Spike -l, including compressed code.

No cache model or branch predictor is inferred from this ISA trace.
"""
import collections
import re

LINE = re.compile(r'core\s+\d+:\s+0x([0-9a-f]+)\s+\(0x([0-9a-f]+)\)')


def categories(bits):
    if bits & 3 == 3:
        op = bits & 127
        return ({3: ('load',), 7: ('load', 'fp'), 35: ('store',),
                 39: ('store', 'fp'), 99: ('branch',), 111: ('direct_jump',),
                 103: ('indirect_jump',), 83: ('fp',), 67: ('fp',),
                 71: ('fp',), 75: ('fp',), 79: ('fp',)}.get(op, ('other',)))
    q, f = bits & 3, (bits >> 13) & 7
    if q in (0, 2):
        memory = {1: ('load', 'fp'), 2: ('load',), 3: ('load',),
                  5: ('store', 'fp'), 6: ('store',), 7: ('store',)}
        if f in memory:
            return memory[f]
    if q == 1 and f in (6, 7):
        return ('branch',)
    if q == 1 and f == 5:
        return ('direct_jump',)
    if q == 2 and f == 4 and (bits >> 7) & 31 and (bits >> 2) & 31 == 0:
        return ('indirect_jump',)
    return ('other',)


def summarize(path):
    counts = collections.Counter()
    previous = None
    for line in path.open(errors='replace'):
        m = LINE.match(line)
        if not m:
            continue
        pc, bits = (int(x, 16) for x in m.groups())
        if previous is not None:
            old_pc, old_length = previous
            counts['branch_transitions'] += 1
            counts['taken_branches'] += pc != old_pc + old_length
        cats = categories(bits)
        counts['instructions'] += 1
        counts.update(cats)
        previous = (pc, 4 if bits & 3 == 3 else 2) if 'branch' in cats else None
    if not counts['instructions']:
        raise ValueError('Spike instruction log is empty')
    return {'scope': 'whole-program including startup and checker',
            'counts': dict(counts), 'cache_misses': None, 'branch_mispredictions': None}
