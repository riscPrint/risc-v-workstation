"""SMT safety proofs with globally consistent uninterpreted datapath functions."""
from hashlib import sha256
import json
import math
from pathlib import Path
import shlex
import shutil
import sys
from .portfolio import race, ENGINES
from .smt_uf import OPERATORS


def wrapper(directory, operators):
    executable = shutil.which('yosys')
    if not executable:
        raise ValueError('Yosys is not installed')
    path = Path(directory) / 'yosys-uf-wrapper'
    code = ('import subprocess, sys\nfrom pathlib import Path\n'
            'from rvw.formal.smt_uf import rewrite_file\n'
            f'proc = subprocess.run([{executable!r}, *sys.argv[1:]])\n'
            'if proc.returncode: raise SystemExit(proc.returncode)\n'
            f'for p in Path.cwd().glob("*.smt2"): rewrite_file(p, {list(operators)!r})\n')
    path.write_text('#!/bin/sh\nunset PYTHONEXECUTABLE PYTHONHOME PYTHONPATH\nexec ' +
                    shlex.quote(sys.executable) + ' -E -c ' + shlex.quote(code) + ' "$@"\n')
    path.chmod(0o755)
    return path


def prove(plan, root, out, *, timeout=15, cross_check=False):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    operators = plan.get('operators', list(OPERATORS))
    if not isinstance(operators, list) or len(set(operators)) != len(operators) or not set(operators) <= set(OPERATORS):
        raise ValueError('operators must be a unique list of bvmul, bvudiv or bvsdiv')
    engines = plan.get('engines', ['smtbmc:yices'])
    if not engines or any(e not in ENGINES or not e.startswith('smtbmc:') or 'prove' not in ENGINES[e][2] for e in engines):
        raise ValueError('UF proofs require SMTBMC prove engines')
    if plan.get('mode', 'prove') != 'prove':
        raise ValueError('UF safety command requires prove mode')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    shim = wrapper(out, operators)
    result = race({**plan, 'engines': engines, 'mode': 'prove'}, root, out / 'native',
                  timeout=timeout, cross_check=cross_check, yosys_executable=shim, smtbmc_logic="QF_AUFBV")
    records = []
    winner = result.get('winner')
    for row in result['rows']:
        if row['status'] == 'cancelled':
            continue
        directory = out / 'native' / row['engine'].replace(':', '_')
        for path in directory.rglob('*.smt2.rvw-uf.json'):
            try:
                record = json.loads(path.read_text())
            except (OSError, ValueError):
                continue  # A timed-out writer cannot provide model capture evidence.
            records.append({'engine': row['engine'], 'path': str(path.relative_to(out)), **record})
    winning = [r for r in records if winner and r['engine'] == winner['engine']]
    applied = sum(f['occurrences'] for r in winning for f in r['functions']) if winner else None
    captured = bool(winning)
    status = 'pass' if captured and result['status'] == 'pass' else 'fail' if captured and not applied and result['status'] == 'fail' else 'inconclusive'
    kind = ('unbounded_uf_overapproximation' if applied else 'unbounded_concrete') if status == 'pass' else 'counterexample' if status == 'fail' else 'none'
    return {'schema': 'rvw.formal-uf-prove/1', 'status': status, 'proof_kind': kind,
            'native_status': result['status'], 'native_result': 'native/result.json',
            'operators': operators, 'rewritten_operations': applied, 'smt_models': records,
            'source_sha256': result['source_sha256'], 'wrapper_sha256': sha256(shim.read_bytes()).hexdigest(),
            'assumptions': result.get('assumptions', []),
            'limits': 'Each operator and bit width uses one global uninterpreted function across all samples. '
                      'Concrete arithmetic is one allowed interpretation. A UF failure is inconclusive. '
                      'Only a captured model with no rewritten operations can report a concrete failure. '
                      'Source environment assumptions remain unqualified. No arithmetic performance gain is claimed.'}
