"""Finite trace candidates. A surviving observation is never a proof."""
import itertools
import re


def mine(signals, traces, groups=(), minimum=2):
    if type(minimum) is not int or minimum < 1:
        raise ValueError('minimum activation count must be positive')
    if not signals or any(not re.fullmatch(r'[A-Za-z_]\w*', name) or
                          type(width) is not int or not 1 <= width <= 64
                          for name, width in signals.items()):
        raise ValueError('declare signal identifiers and widths from 1 to 64')
    booleans = [name for name, width in signals.items() if width == 1]
    specs = [('implies', (a,b)) for a in booleans for b in booleans if a != b]
    specs += [('mutex', pair) for pair in itertools.combinations(booleans, 2)]
    specs += [('stable', (guard, value)) for guard in booleans for value in signals if guard != value]
    for group in groups:
        if len(group) < 2 or len(set(group)) != len(group) or set(group) - set(booleans):
            raise ValueError('one-hot sets need distinct declared Boolean signals')
        specs += [('onehot0', tuple(group))]
    counts = [[0, {s:0 for s in names}] for _, names in specs]
    rejected = set()
    samples = boundaries = 0
    for trace in traces:
        previous = None
        boundaries += 1
        for row in trace:
            if any(type(row.get(name)) is not int or not 0 <= row[name] < 2**width
                   for name, width in signals.items()):
                raise ValueError('missing, unknown or out-of-width signal sample')
            samples += 1
            for index, (kind, names) in enumerate(specs):
                if index in rejected:
                    continue
                active = False
                good = True
                if kind == 'implies':
                    active = bool(row[names[0]])
                    good = not active or bool(row[names[1]])
                elif kind == 'stable' and previous is not None:
                    active = bool(previous[names[0]])
                    good = not active or row[names[1]] == previous[names[1]]
                elif kind in ('mutex', 'onehot0'):
                    active = any(row[name] for name in names)
                    good = sum(row[name] for name in names) <= 1
                if not good:
                    rejected.add(index)
                if active:
                    counts[index][0] += 1
                for name in names:
                    counts[index][1][name] += bool(row[name])
            previous = row
    if not samples:
        raise ValueError('mining needs nonempty traces')
    candidates = []
    inactive = 0
    for index, (kind, names) in enumerate(specs):
        if index in rejected:
            continue
        activated, members = counts[index]
        if activated < minimum or kind in ('mutex','onehot0') and min(members.values()) < minimum:
            inactive += 1
            continue
        candidates.append(dict(id=f'trace_{index}', kind=kind, signals=list(names),
                               activated=activated, member_hits=members,
                               status='observed_candidate'))
    return dict(schema='rvw.trace-candidates/1', status='candidates' if candidates else 'no_candidates',
                samples=samples, traces=boundaries, candidates=candidates,
                refuted=len(rejected), inactive=inactive,
                scope='supplied finite traces only; candidates need review and fresh formal checks')


def scala(report):
    lines = ['import spinalchecks.Sva._', 'object MinedProperties {',
             '  def statements(clock: Expr, reset: Option[Expr]): Seq[String] = Seq(']
    statements = []
    for row in report['candidates']:
        names = [f'signal("{s}")' for s in row['signals']]
        if row['kind'] == 'implies':
            expr = f'{names[0]}.sequence.implies({names[1]}.sequence)'
        elif row['kind'] == 'stable':
            expr = f'{names[0]}.sequence.implies({names[1]}.equal({names[1]}.past).sequence, overlap = false)'
        else:
            pairs = [f'!({a} && {b})' for a,b in itertools.combinations(names, 2)]
            expr = '(' + ' && '.join(pairs) + ').sequence.property'
        statements.append(f'    {expr}.assertOn("{row["id"]}", clock, reset)')
    return '\n'.join(lines + [',\n'.join(statements), '  )', '}', ''])
