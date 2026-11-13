"""Explainable engine ordering from elaborated cells and qualified history."""


def features(design):
    result = dict(state_bits=0, memories=0, arithmetic=0, counters=0, liveness=0)
    for module in design['modules'].values():
        for cell in module.get('cells', {}).values():
            kind = cell['type']
            if kind.startswith(('$dff', '$sdff', '$adff', '$ff')):
                result['state_bits'] += len(cell.get('connections', {}).get('Q', []))
            result['memories'] += int(kind.startswith('$mem'))
            result['arithmetic'] += int(kind in ('$mul', '$div', '$divfloor', '$mod', '$modfloor'))
            result['counters'] += int(kind == '$add')
            result['liveness'] += int(kind in ('$live', '$fair') or
                kind == '$check' and cell.get('parameters', {}).get('FLAVOR') in ('live', 'fair'))
    return result


def select(design, histories=()):
    f = features(design)
    engines = ['abc:pdr', 'aiger:rIC3', 'smtbmc:yices', 'smtbmc:bitwuzla']
    reasons = ['Boolean safety starts with PDR and rIC3.']
    if f['memories'] or f['arithmetic']:
        engines = ['smtbmc:yices', 'smtbmc:bitwuzla', 'abc:pdr', 'aiger:rIC3']
        reasons.append('Memory or arithmetic cells put word-level engines first.')
    samples = {}
    for history in histories:
        for row in history.get('rows', []):
            # Benchmark problem verdict, not native conditional or bounded answers.
            if row.get('problem_status') not in ('pass', 'fail'):
                continue
            engine = row.get('engine')
            elapsed = row.get('total_wall_s')
            if engine not in engines or not isinstance(elapsed, (int, float)) or elapsed <= 0:
                continue
            solved, wall = samples.get(engine, (0, 0.0))
            samples[engine] = solved + 1, wall + elapsed
    if samples:
        prior = {e: i for i, e in enumerate(engines)}
        engines.sort(key=lambda e: (-samples.get(e, (0, 0))[0],
                                    samples[e][1] / samples[e][0] if e in samples else float('inf'), prior[e]))
        reasons.append('Qualified recorded solves rank first, then mean wall time per solve.')
    abstractions = []
    if f['memories']: abstractions.append('lazy-ram')
    if f['arithmetic']: abstractions.append('uf-prove')
    if f['counters']: abstractions.append('counter-quotient_requires_leaf_binding')
    if f['state_bits'] > 256: abstractions.append('rtl-refine')
    if f['liveness']:
        engines = []
        abstractions = ['liveness-to-safety', 'k-live']
        reasons.append('Native liveness cells need a supported liveness reduction before a safety race.')
    return {'schema': 'rvw.formal-strategy/1', 'status': 'planned', 'features': f,
            'engines': engines, 'abstractions': abstractions, 'history_samples': samples,
            'reasons': reasons, 'limits': 'Ordering advice only. No proof or abstraction was run. '
            'State bits are an elaborated cell inventory, not reachable state. '
            'History applies to supplied workloads; it does not predict another core.'}
