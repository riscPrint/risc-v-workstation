"""Pinned input head-to-head measurements. Each engine runs alone."""
import json
from pathlib import Path
import re
import time
from .portfolio import race, ENGINES


def benchmark(plan, root, out, timeout):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    rows = []
    seen = set()
    for case in plan['cases']:
        name = case['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or name in seen:
            raise ValueError('case IDs must be unique simple names')
        seen.add(name)
        for engine in plan.get('engines', list(ENGINES)):
            began = time.monotonic()
            report = race({**case, 'engines': [engine]}, root, out / name / engine.replace(':', '_'), timeout=timeout)
            rows.append({'case': name, 'engine': engine, 'total_wall_s': time.monotonic() - began, **(report['rows'][0] if report['rows'] else {'status': report['status'], 'reason': report.get('reason'), 'wall_s': None}),
                         'source_sha256': report['source_sha256'], 'mode': report['mode'], 'depth': report['depth']})
    agreement = {}
    for case in seen:
        verdicts = [r['status'] for r in rows if r['case'] == case and r['status'] in ('pass', 'fail')]
        agreement[case] = 'disagree' if len(set(verdicts)) > 1 else 'agree' if len(verdicts) > 1 else 'inconclusive'
    summary = {}
    for engine in plan.get('engines', list(ENGINES)):
        selected = [r for r in rows if r['engine'] == engine]
        summary[engine] = {'solved': sum(r['status'] in ('pass', 'fail') for r in selected),
                           'bounded_passes': sum(r['status'] == 'bounded_pass' for r in selected),
                           'cases': len(selected), 'wall_s': sum(r['total_wall_s'] for r in selected)}
    return {'summary': summary, 'schema': 'rvw.formal-engine-bench/1', 'status': 'pass' if agreement and all(s == 'agree' for s in agreement.values()) else 'inconclusive',
            'rows': rows, 'agreement': agreement,
            'limits': 'Wall time includes preparation. Requested depth is not measured depth. No capacity or commercial parity claim.'}
