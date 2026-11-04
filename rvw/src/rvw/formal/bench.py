"""Pinned same-input engine measurements. Missing measurements stay null."""
from hashlib import sha256
from pathlib import Path
import json
import math
import shutil
import sys
import re
import time

from rvw.common.proc import run_group

from . import common
from .apps import ident

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


def measure(sources, case, engine, target, timeout):
    """Measure the complete command. Native time reports process-tree maximum RSS."""
    command = [sys.executable, '-m', 'rvw', 'formal', case['mode'], '--verilog',
               *map(str, sources), '--top', case['top'], '--clock', case['clock'],
               '--reset', case['reset'], '--out', str(target), '--depth', str(case['depth']),
               '--engine', engine, '--timeout', str(timeout)]
    timer = Path('/usr/bin/time')
    if timer.exists():
        command = [str(timer), '-l' if sys.platform == 'darwin' else '-v', *command]
    started = time.monotonic()
    # Allow frontend, reachability and capture overhead beyond the solver timeout.
    process = run_group(command, capture=True, timeout=timeout * 4 + 30)
    elapsed = time.monotonic() - started
    path = target / 'result.json'
    if not path.exists():
        return {'status': 'timeout' if process.timed_out else 'error', 'wall_s': elapsed,
                'reason': (process.stderr or '')[-2000:]}
    result = json.loads(path.read_text())
    if process.timed_out or process.returncode not in (0, 1):
        result['status'] = 'timeout' if process.timed_out else 'error'
    memory = None
    if timer.exists():
        if sys.platform == 'darwin':
            match = re.search(r'(\d+)\s+maximum resident set size', process.stderr or '')
            memory = int(match[1]) if match else None
        else:
            match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', process.stderr or '')
            memory = int(match[1]) * 1024 if match else None
    log = target / 'sby/logfile.txt'
    steps = re.findall(r'Checking assertions in step (\d+)', log.read_text() if log.exists() else '')
    result.update(wall_s=elapsed, peak_memory_bytes=memory,
                  reached_depth=max(map(int, steps)) if steps else None)
    (target.parent / (target.name + '.measurement.log')).write_text(
        (process.stdout or '') + (process.stderr or ''))
    return result


def licensed_adapter(adapter, sources, case, directory, timeout):
    """Observe an explicitly configured local adapter. It owns licence setup."""
    from rvw.common.capture import Capture
    capture = Capture(directory / 'adapter-inputs')
    tool = capture.tool(adapter['command'])
    request = {'schema': 'rvw.formal-adapter-request/1',
               'case': case, 'sources': [str(p) for p in sources]}
    payload = json.dumps(request, sort_keys=True)
    digest = sha256(payload.encode()).hexdigest()
    request_path = directory / 'request.json'
    request_path.write_text(payload)
    response_path = directory / 'response.json'
    process = run_group([tool.path, str(request_path), str(response_path)],
                        capture=True, timeout=timeout)
    row = {'case': case['id'], 'engine': adapter['id'], 'mode': case['mode'],
           'status': 'inconclusive', 'wall_s': None, 'peak_memory_bytes': None,
           'reached_depth': None, 'evidence_kind': 'trusted_adapter_observation',
           'tools': capture.record()}
    (directory / 'adapter.log').write_text((process.stdout or '') + (process.stderr or ''))
    if process.returncode or process.timed_out or not response_path.exists():
        return row
    response = json.loads(response_path.read_text())
    if (response.get('schema') != 'rvw.formal-adapter-response/1'
            or response.get('request_sha256') != digest
            or response.get('status') not in ('pass', 'fail', 'inconclusive')
            or response.get('mode') != case['mode']):
        return row
    for key in ('wall_s', 'peak_memory_bytes', 'reached_depth'):
        value = response.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            return row
    if not isinstance(response.get('engine_version'), str) or not response['engine_version']:
        return row
    row.update({k: response[k] for k in ('status', 'wall_s', 'peak_memory_bytes',
                                       'reached_depth', 'engine_version')})
    return row


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
    adapters = plan.get('adapters', [])
    for adapter in adapters:
        ident(adapter['id'])
        if adapter['id'] in ENGINES or not Path(adapter['command']).is_absolute():
            raise ValueError('adapter needs unique ID and absolute executable path')
    if len({a['id'] for a in adapters}) != len(adapters):
        raise ValueError('duplicate adapter ID')
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
                    result = measure(sources, case, engine, target, args.timeout)
                    row.update(status=result['status'], wall_s=result['wall_s'],
                               tools=result.get('tools'), peak_memory_bytes=result.get('peak_memory_bytes'),
                               reached_depth=result.get('reached_depth'), reason=result.get('reason'), result=str(target.relative_to(out) / 'result.json'))
                    # Requested depth is not an observed engine depth.
                except (ValueError, OSError, SystemExit) as exc:
                    row.update(status='error', reason=str(exc))
            rows.append(row)
        for adapter in adapters:
            adapter_dir = directory / adapter['id']
            adapter_dir.mkdir()
            rows.append(licensed_adapter(adapter, sources, case, adapter_dir, args.timeout))
    agreement = []
    for case, _ in cases:
        samples = [r for r in rows if r['case'] == case['id'] and r['status'] not in ('not_installed', 'unsupported_mode')]
        decisive = {r['status'] for r in samples if r['status'] in ('pass', 'fail')}
        status = 'disagree' if len(decisive) > 1 else (
            'agree' if len(samples) >= 2 and all(r['status'] in ('pass', 'fail') for r in samples) else 'inconclusive')
        agreement.append({'case': case['id'], 'status': status})
    baseline = plan.get('baseline', 'smtbmc:yices')
    report = {'schema': 'rvw.formal-bench-results/1', 'rows': rows, 'agreement': agreement,
              'comparisons': {e: compare(rows, baseline, e) for e in [*installed, *(a['id'] for a in adapters)] if e != baseline},
              'limits': 'Wall time includes frontend, capture and reachability checks. Peak memory is native time RSS. '
                        'Reached depth is the largest explicitly logged assertion step, otherwise null. Installed unsupported engines are not silently counted as passes. '
                        'Licensed adapters supply trusted observations, not independently replayed proofs. No published-result comparison.'}
    common.write_json(out / 'result.json', report)
    print(json.dumps(report, indent=2) if args.json else str(out / 'result.json'))
    return 0 if all(a['status'] == 'agree' for a in agreement) else 1
