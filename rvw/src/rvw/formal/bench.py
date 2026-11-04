"""Pinned same-input engine measurements. Missing measurements stay null."""
from hashlib import sha256
from pathlib import Path
import json
import math
import shutil

from . import common
from .apps import flow, ident

ENGINES = {'smtbmc:yices': 'yices-smt2', 'smtbmc:z3': 'z3',
           'smtbmc:bitwuzla': 'bitwuzla', 'smtbmc:boolector': 'boolector',
           'smtbmc:cvc4': 'cvc4', 'smtbmc:cvc5': 'cvc5', 'smtbmc:mathsat': 'mathsat',
           'abc:bmc3': 'yosys-abc', 'abc:pdr': 'yosys-abc',
           'aiger:avy': 'avy', 'btor:pono': 'pono', 'btor:btormc': 'btormc'}


def compare(rows, baseline, candidate, margin=0.05):
    """Descriptive paired comparison, never a statistical or commercial parity claim."""
    pairs = {}
    for row in rows:
        pairs.setdefault(row['case'], {})[row['engine']] = row
    ratios = []
    for pair in pairs.values():
        a, b = pair.get(baseline), pair.get(candidate)
        if (not a or not b or a['status'] not in ('pass', 'fail') or a['status'] != b['status']
                or a.get('wall_s') is None or b.get('wall_s') is None or a['wall_s'] <= 0):
            return {'status': 'inconclusive', 'reason': 'missing, unresolved or disagreeing pair'}
        ratios.append(b['wall_s'] / a['wall_s'])
    if not ratios:
        return {'status': 'inconclusive', 'reason': 'no paired measurements'}
    return {'status': 'measured', 'paired_cases': len(ratios), 'margin': margin,
            'worst_time_ratio': max(ratios),
            'noninferior_on_suite': max(ratios) <= 1 + margin,
            'superior_on_suite': max(ratios) < 1 - margin,
            'scope': 'All paired cases in this run; no population or commercial parity inference'}


def run(args):
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('timeout must be positive and finite')
    path = Path(args.manifest).resolve()
    plan = json.loads(path.read_text())
    if plan.get('schema') != 'rvw.formal-bench/1' or not plan.get('cases'):
        raise ValueError('expected rvw.formal-bench/1 with cases')
    cases, ids = [], set()
    # Hash-check all inputs before any engine runs.
    for case in plan['cases']:
        name = ident(case['id'])
        if name in ids:
            raise ValueError('duplicate benchmark case ID')
        ids.add(name)
        files = []
        for source in case['sources']:
            original = (path.parent / source['path']).resolve()
            data = original.read_bytes()
            if sha256(data).hexdigest() != source['sha256']:
                raise ValueError('benchmark source hash mismatch: ' + str(original))
            if b'`include' in data or b'$readmem' in data:
                raise ValueError('benchmark requires self-contained exported RTL')
            files.append(data)
        if not files or case['mode'] not in ('bmc', 'prove') or type(case['depth']) is not int or case['depth'] < 2:
            raise ValueError('case needs sources, mode bmc/prove and depth >= 2')
        for key in ('top', 'clock', 'reset'):
            ident(case[key])
        cases.append((case, files))
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    common.write_json(out / 'manifest.json', plan)
    rows = []
    installed = {e: shutil.which(tool) for e, tool in ENGINES.items()}
    for case, files in cases:
        directory = out / case['id']
        directory.mkdir()
        sources = []
        for i, data in enumerate(files):
            source = directory / f'source{i}.sv'
            source.write_bytes(data)
            sources.append(source)
        for engine, executable in installed.items():
            row = {'case': case['id'], 'engine': engine, 'mode': case['mode'],
                   'requested_depth': case['depth'], 'reached_depth': None,
                   'peak_memory_bytes': None, 'wall_s': None, 'status': 'not_installed'}
            incompatible = (case['mode'] == 'prove' and engine in ('abc:bmc3', 'btor:btormc') or
                            case['mode'] == 'bmc' and engine in ('abc:pdr', 'aiger:avy'))
            if executable and incompatible:
                row['status'] = 'unsupported_mode'
            elif executable:
                target = directory / engine.replace(':', '_')
                try:
                    result = flow(sources, case['top'], case['clock'], case['reset'], target,
                                  case['depth'], engine, args.timeout, case['mode'])
                    row.update(status=result['status'], wall_s=result['wall_s'],
                               tools=result.get('tools'), result=str(target.relative_to(out) / 'result.json'))
                    # Requested depth is not an observed engine depth.
                except (ValueError, OSError, SystemExit) as exc:
                    row.update(status='error', reason=str(exc))
            rows.append(row)
    agreement = []
    for case, _ in cases:
        samples = [r for r in rows if r['case'] == case['id'] and r['status'] not in ('not_installed', 'unsupported_mode')]
        decisive = {r['status'] for r in samples if r['status'] in ('pass', 'fail')}
        status = 'disagree' if len(decisive) > 1 else (
            'agree' if len(samples) >= 2 and all(r['status'] in ('pass', 'fail') for r in samples) else 'inconclusive')
        agreement.append({'case': case['id'], 'status': status})
    baseline = plan.get('baseline', 'smtbmc:yices')
    report = {'schema': 'rvw.formal-bench-results/1', 'rows': rows, 'agreement': agreement,
              'comparisons': {e: compare(rows, baseline, e) for e in installed if e != baseline},
              'limits': 'Wall time includes frontend, capture and reachability checks. Peak memory and reached '
                        'depth are not collected. Installed unsupported engines are not silently counted as passes. '
                        'No licensed commercial adapter or published-result comparison in this increment.'}
    common.write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else str(out / 'result.json'))
    return 0 if all(a['status'] == 'agree' for a in agreement) else 1
