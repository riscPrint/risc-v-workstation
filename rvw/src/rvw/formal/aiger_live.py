"""Native rIC3 liveness and safety-reduction orchestration."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import time

from rvw.common.proc import run_group
from . import aiger_live_model


def native(path, directory, engine, executable, timeout):
    directory.mkdir()
    command = ['nice', '-n', '10', executable, '-e', engine, str(path), '--witness']
    env = dict(os.environ)
    env.pop('RIC3_WORKER', None)
    start = time.monotonic()
    result = run_group(command, cwd=directory, env=env, capture=True, timeout=timeout)
    stdout, stderr = result.stdout or '', result.stderr or ''
    (directory / 'stdout.log').write_text(stdout)
    (directory / 'stderr.log').write_text(stderr)
    clean = re.sub(r'\x1b\[[0-9;]*m', '', stdout)
    answers = re.findall(r'^(SAT|UNSAT|UNKNOWN)\s*$', clean, re.M)
    expected = {10: 'SAT', 20: 'UNSAT', 30: 'UNKNOWN'}
    answer = answers[0] if len(answers) == 1 and expected.get(result.returncode) == answers[0] else None
    status = 'timeout' if result.timed_out else {'SAT': 'unsafe', 'UNSAT': 'safe', 'UNKNOWN': 'inconclusive'}.get(answer, 'error')
    from .engine_limits import rlive_failure
    diagnostic = rlive_failure(stdout, stderr) if engine == 'rlive' and status == 'error' else {}
    return {**diagnostic, 'status': status, 'returncode': result.returncode, 'wall_s': time.monotonic() - start,
            'command': command, 'engine': engine, 'stdout': str(directory / 'stdout.log'),
            'stderr': str(directory / 'stderr.log'), 'model_sha256': sha256(path.read_bytes()).hexdigest()}


def check(plan, root, out, *, method='l2s', k=2, timeout=15):
    if method not in ('l2s', 'k-live', 'rlive'):
        raise ValueError('method must be l2s, k-live or rlive')
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    if type(k) is not int or not 1 <= k <= 1024:
        raise ValueError('k must be in 1..1024')
    data = (Path(root) / plan['path']).read_bytes()
    digest = sha256(data).hexdigest()
    if digest != plan['sha256']:
        raise ValueError('AIGER source hash mismatch')
    model = aiger_live_model.read(data.decode('ascii'))
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'source.aag'
    source.write_bytes(data)
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    report = {'schema': 'rvw.formal-aiger-live/1', 'status': 'inconclusive', 'proof_kind': 'none',
              'method': method, 'k': k if method == 'k-live' else None, 'source_sha256': digest,
              'reducer_sha256': sha256(Path(aiger_live_model.__file__).read_bytes()).hexdigest(),
              'source_latches': len(model.latches), 'justice': model.justice, 'fairness': model.fairness,
              'constraints': model.constraints, 'stages': [], 'fairness_check': 'not_run',
              'limits': 'One AIGER bad justice group describes a fair accepting infinite execution. '
                        'L2S preserves the full finite state and all invariant constraints. '
                        'K-liveness is sufficient only; reaching k rounds is inconclusive. '
                        'rIC3 rlive is experimental. Source-language translation and independent '
                        'certificate validation are not established.'}
    executable = shutil.which('rIC3')
    if not executable:
        return {**report, 'reason': 'not_installed'}
    report['tool'] = {'path': executable, 'sha256': sha256(Path(executable).read_bytes()).hexdigest()}
    path = source
    if method != 'rlive':
        text, reduction = aiger_live_model.reduce(model, method, k)
        path = out / 'property.aag'
        path.write_text(text)
        report['reduction'] = reduction
    row = native(path, out / 'property', 'rlive' if method == 'rlive' else 'ic3', executable, timeout)
    report['stages'].append({'purpose': 'property', **row})
    if row['status'] == 'unsafe':
        if method == 'k-live':
            report['reason'] = 'k_bound_reached'
        else:
            report.update(status='fail', proof_kind='fair_accepting_cycle', fairness_check='counterexample_is_fair')
        return report
    if row['status'] != 'safe':
        return {**report, 'reason': row.get('reason', row['status'])}
    if model.constraints or model.fairness:
        # Avoid a proof that is true only because no allowed fair path exists.
        text, reduction = aiger_live_model.reduce(model, 'l2s', feasibility=True)
        fair_path = out / 'fairness.aag'
        fair_path.write_text(text)
        fair = native(fair_path, out / 'fairness', 'ic3', executable, timeout)
        report['stages'].append({'purpose': 'fairness_feasibility', 'reduction': reduction, **fair})
        report['fairness_check'] = 'feasible' if fair['status'] == 'unsafe' else 'infeasible' if fair['status'] == 'safe' else 'inconclusive'
        if fair['status'] != 'unsafe':
            return {**report, 'reason': 'fairness_' + report['fairness_check']}
    else:
        report['fairness_check'] = 'total_finite_transition_system'
    report.update(status='pass', proof_kind={'l2s': 'liveness_to_safety', 'k-live': 'k_liveness', 'rlive': 'native_rlive'}[method])
    return report
