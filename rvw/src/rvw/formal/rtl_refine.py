"""Automatic unconstrained RTL cuts with conservative refinement.

Every cut removes a driver, so proofs cover an overapproximation. An abstract
counterexample only requests refinement. Only a cut-free failure is concrete.
"""
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys
import time
from rvw.common.proc import run_group

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z')


def select_cuts(module, clock='clk', reset='reset', limit=8):
    excluded = {b for name, p in module['ports'].items() for b in p['bits']}
    candidates = []
    used = set()
    nets = module.get('netnames', {})
    for cell in module.get('cells', {}).values():
        kind = cell['type']
        ports = cell.get('connections', {})
        outputs = [('RD_DATA', 'memory-read')] if kind in ('$mem_v2', '$memrd', '$memrd_v2') else [('Q', 'state')] if kind.startswith(('$dff', '$adff', '$sdff', '$ff')) else []
        for port, role in outputs:
            bits = ports.get(port, [])
            if not bits or any(type(b) is not int for b in bits) or set(bits) & (excluded | used):
                continue
            names = sorted(n for n, v in nets.items() if v['bits'] == bits and IDENT.fullmatch(n))
            if not names:
                continue
            name = names[0]
            if name in (clock, reset) or len(set(bits)) != len(bits):
                continue
            candidates.append({'signal': name, 'width': len(bits), 'kind': role})
            used.update(bits)
    return sorted(candidates, key=lambda r: (r['kind'] != 'memory-read', -r['width'], r['signal']))[:limit]


def refine(plan, root, out, *, budget=60, timeout=15, max_cuts=8):
    from .portfolio import ENGINES
    if not all(math.isfinite(v) and v > 0 for v in (budget, timeout)) or max_cuts < 0:
        raise ValueError('positive finite budgets and nonnegative max_cuts required')
    top = plan['top']
    if not IDENT.fullmatch(top) or '.' in top:
        raise ValueError('invalid top')
    engine = plan.get('engine', 'smtbmc:yices')
    if engine not in ENGINES or engine == 'ebmc' or 'prove' not in ENGINES[engine][2]:
        raise ValueError('refinement needs an unbounded SBY engine')
    clock, reset = plan.get('clock', 'clk'), plan.get('reset')
    if not IDENT.fullmatch(clock) or (reset is not None and not IDENT.fullmatch(reset)):
        raise ValueError('invalid clock or reset')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = []
    for i, item in enumerate(plan['sources']):
        data = (Path(root) / item['path']).read_bytes()
        if sha256(data).hexdigest() != item['sha256']:
            raise ValueError('source hash mismatch')
        if b'`include' in data or b'$readmem' in data:
            raise ValueError('refinement needs self-contained RTL')
        p = out / f'input{i}.sv'
        p.write_bytes(data)
        sources.append(p)
    if not sources:
        raise ValueError('no RTL sources')
    deadline = time.monotonic() + budget
    script = 'read -formal ' + ' '.join(p.name for p in sources) + '; hierarchy -check -top ' + top + '; proc; flatten; opt_clean; memory_collect; write_json inspect.json'
    process = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=min(timeout, budget))
    (out / 'inspect.log').write_text((process.stdout or '') + (process.stderr or ''))
    inspect = out / 'inspect.json'
    if process.returncode or process.timed_out or not inspect.exists():
        raise ValueError('cannot inspect RTL for automatic cuts')
    cuts = select_cuts(json.loads(inspect.read_text())['modules'][top], clock, reset, max_cuts)
    initial = list(cuts)
    rows = []
    status, proof_kind = 'inconclusive', 'none'
    for i in range(len(cuts) + 2):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        target = out / f'round-{i}'
        command = [sys.executable, '-m', 'rvw', 'formal', 'prove', '--verilog', *map(str, sources),
                   '--top', top, '--clock', clock, '--engine', engine,
                   '--depth', str(plan.get('depth', 20)), '--timeout', str(min(timeout, remaining)), '--out', str(target)]
        if reset is not None:
            command += ['--reset', reset]
        for cut in cuts:
            command += ['--cut', f"{cut['signal']}:{cut['width']}"]
        child = run_group(command, capture=True, timeout=max(.001, remaining))
        (out / f'round-{i}.log').write_text((child.stdout or '') + (child.stderr or ''))
        result_file = target / 'result.json'
        result = json.loads(result_file.read_text()) if result_file.exists() else {}
        row = {'engine': engine, 'cuts': list(cuts), 'status': result.get('status', 'inconclusive'),
               'proof_kind': result.get('proof_kind'), 'result': str(result_file)}
        rows.append(row)
        if child.timed_out or child.returncode not in (0, 1):
            row['status'] = 'inconclusive'
            break
        if result.get('status') == 'pass' and result.get('proof_kind') == 'unbounded':
            status, proof_kind = 'pass', 'unbounded'
            break
        if not cuts and result.get('status') == 'fail':
            status, proof_kind = 'fail', 'counterexample'
            break
        if cuts and result.get('abstraction_counterexample'):
            row['status'] = 'inconclusive'
            row['proof_kind'] = 'abstraction'
            row['reason'] = 'abstraction_only_counterexample'
            row['restored_driver'] = cuts.pop()
            continue
        if not cuts and result.get('status') in ('unknown', 'inconclusive') and engine != 'abc:pdr':
            row['reason'] = 'induction_inconclusive_try_pdr'
            engine = 'abc:pdr'
            continue
        break
    report = {'schema': 'rvw.formal-rtl-refine/1', 'status': status, 'proof_kind': proof_kind,
              'initial_cuts': initial, 'rounds': rows,
              'source_sha256': [sha256(p.read_bytes()).hexdigest() for p in sources],
              'limits': 'Cuts abstract internal state and RAM read outputs without adding memory assumptions. '
                        'Refinement restores one driver per abstract counterexample. No liveness or activation proof.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
