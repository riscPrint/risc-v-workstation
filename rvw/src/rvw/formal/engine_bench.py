"""Pinned input head-to-head measurements. Each engine runs alone."""
import json
from pathlib import Path
import re
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
            report = race({**case, 'engines': [engine]}, root, out / name / engine.replace(':', '_'), timeout=timeout)
            rows.append({'case': name, 'engine': engine, **(report['rows'][0] if report['rows'] else {'status': report['status'], 'reason': report.get('reason'), 'wall_s': None}),
                         'source_sha256': report['source_sha256'], 'mode': report['mode'], 'depth': report['depth']})
    agreement = {}
    for case in seen:
        verdicts = [r['status'] for r in rows if r['case'] == case and r['status'] in ('pass', 'fail')]
        agreement[case] = 'disagree' if len(set(verdicts)) > 1 else 'agree' if len(verdicts) > 1 else 'inconclusive'
    return {'schema': 'rvw.formal-engine-bench/1', 'status': 'pass' if agreement and all(s == 'agree' for s in agreement.values()) else 'inconclusive',
            'rows': rows, 'agreement': agreement,
            'limits': 'Wall time includes preparation. Requested depth is not measured depth. No capacity or commercial parity claim.'}
