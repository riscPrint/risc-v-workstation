"""Budgeted bounded search with engine and rIC3 seed diversity."""
from hashlib import sha256
import json
import math
from pathlib import Path
import time
from .portfolio import race, ENGINES


def hunt(plan, root, out, *, budget=60, timeout=15):
    if any(not math.isfinite(x) or x <= 0 for x in (budget, timeout)):
        raise ValueError('budget and timeout must be finite and positive')
    depths = plan.get('depths', [20, 40, 80])
    seeds = plan.get('seeds', [0, 1])
    engines = plan.get('engines', ['aiger:rIC3', 'abc:bmc3', 'smtbmc:yices'])
    if not depths or any(type(d) is not int or d < 1 for d in depths) or depths != sorted(set(depths)):
        raise ValueError('depths must be increasing positive integers')
    if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int or not 0 <= s < 2**64 for s in seeds):
        raise ValueError('seeds must be unique unsigned 64-bit integers')
    if not engines or len(set(engines)) != len(engines) or any(e not in ENGINES or 'bmc' not in ENGINES[e][2] for e in engines):
        raise ValueError('engines must be unique bounded engine IDs')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    sources = out / 'inputs'
    sources.mkdir()
    frozen = []
    for i, source in enumerate(plan['sources']):
        data = (Path(root) / source['path']).read_bytes()
        if sha256(data).hexdigest() != source['sha256']:
            raise ValueError('source hash mismatch')
        path = sources / f'{i}.input'
        path.write_bytes(data)
        frozen.append({**source, 'path': path.name})
    schedule = [{'engine': e, 'depth': d, 'seed': s if e == 'aiger:rIC3' else None}
                for d in depths for e in engines for s in (seeds if e == 'aiger:rIC3' else [None])]
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    deadline = time.monotonic() + budget
    attempts, stop = [], 'schedule_complete'
    for task in schedule:
        left = deadline - time.monotonic()
        if left <= 0:
            stop = 'budget_exhausted'
            break
        child = {**plan, 'sources': frozen, 'engines': [task['engine']], 'mode': 'bmc',
                 'depth': task['depth'], 'ric3_seed': task['seed']}
        directory = out / f'attempt-{len(attempts)}'
        # Reserve time for preparation, compatibility probing and engine execution.
        result = race(child, sources, directory, timeout=min(timeout, left / 3))
        attempts.append({**task, 'status': result['status'], 'rows': result['rows'],
                         'result': str(directory.relative_to(out) / 'result.json')})
        if result['status'] == 'fail':
            stop = 'counterexample'
            break
    report = {'schema': 'rvw.formal-bug-hunt/1', 'status': 'fail' if stop == 'counterexample' else 'inconclusive',
              'proof_kind': 'counterexample' if stop == 'counterexample' else 'none',
              'stop_reason': stop, 'attempts': attempts, 'unstarted': schedule[len(attempts):],
              'budget_s': budget, 'source_sha256': [s['sha256'] for s in frozen],
              'limits': 'Bounded search only. A completed schedule cannot prove safety. '
                        'Seeds diversify rIC3 only. Source assertions and assumptions define the problem. '
                        'No cover reachability or reset certification is added.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
