"""Retirement-order pairs. These observations do not measure pipeline stalls."""


KINDS = ['RAW', 'WAW', 'WAR', 'branch-after-load', 'load-after-load',
         'store-after-load', 'load-after-store', 'store-after-store',
         'branch-after-branch', 'jump-after-branch', 'branch-after-jump', 'jump-after-jump']


def groups(settings):
    distances = settings.get('distances', [1, 2, 4])
    if (not distances or any(type(d) is not int or not 1 <= d <= 256 for d in distances)
            or len(set(distances)) != len(distances)):
        raise ValueError('sequence distances must be distinct integers in 1..256')
    kinds = settings.get('kinds', KINDS)
    if not kinds or len(set(kinds)) != len(kinds) or set(kinds) - set(KINDS):
        raise ValueError('unsupported sequence kinds')
    return [{'name': 'sequence', 'fields': ['kind', 'distance'],
             'when': {'event': 'sequence'},
             'bins': [[kind, d] for d in distances for kind in kinds]}]


def observe(history, row, info, dest, distances, selected=None):
    """Reset at gaps, traps, handler entry or unknown instructions. x0 is not a producer."""
    if (row.get('trap') or row.get('intr') or info['class'] == 'unknown'
            or dest == 'undetermined'):
        history.clear()
        return []
    if history and row['order'] != history[-1]['order'] + 1:
        history.clear()
    uses = {tuple(r) for r in info['uses'] if tuple(r) != ('x', 0)}
    result = []
    for older in history:
        distance = row['order'] - older['order']
        if distance not in distances:
            continue
        kinds = []
        if older['dest'] and older['dest'] in uses:
            kinds.append('RAW')
        if dest and dest == older['dest']:
            kinds.append('WAW')
        if dest and dest in older['uses']:
            kinds.append('WAR')
        before, after = older['class'], info['class']
        if before == 'load' and after == 'branch':
            kinds.append('branch-after-load')
        if before in ('branch', 'jump') and after in ('branch', 'jump'):
            kinds.append(f'{after}-after-{before}')
        if before in ('load', 'store') and after in ('load', 'store'):
            kinds.append(f'{after}-after-{before}')
        result += [{'event': 'sequence', 'kind': k, 'distance': distance} for k in kinds if selected is None or k in selected]
    history.append({'order': row['order'], 'uses': uses, 'dest': dest, 'class': info['class']})
    history[:] = history[-max(distances):]
    return result
