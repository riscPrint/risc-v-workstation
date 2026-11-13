"""Race independent native engines on identical self-contained RTL bytes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import shlex
import signal
import threading
import time

from rvw.common.proc import run_group

# Backend, executable dependencies, supported modes.
ENGINES = {
    'smtbmc:yices': ('sby', ('sby', 'yosys', 'yosys-smtbmc', 'yices-smt2'), ('prove', 'bmc')),
    'smtbmc:z3': ('sby', ('sby', 'yosys', 'yosys-smtbmc', 'z3'), ('prove', 'bmc')),
    'smtbmc:bitwuzla': ('sby', ('sby', 'yosys', 'yosys-smtbmc', 'bitwuzla'), ('prove', 'bmc')),
    'smtbmc:cvc5': ('sby', ('sby', 'yosys', 'yosys-smtbmc', 'cvc5'), ('prove', 'bmc')),
    'btor:btormc': ('sby', ('sby', 'yosys', 'btormc', 'btorsim'), ('bmc',)),
    'aiger:suprove': ('sby', ('sby', 'yosys', 'suprove'), ('prove',)),
    'abc:pdr': ('sby', ('sby', 'yosys', 'yosys-abc'), ('prove',)),
    'abc:bmc3': ('sby', ('sby', 'yosys', 'yosys-abc'), ('bmc',)),
    'btor:pono': ('sby', ('sby', 'yosys', 'pono', 'btorsim'), ('bmc',)),
    'aiger:avy': ('sby', ('sby', 'yosys', 'yosys-abc', 'avy'), ('prove',)),
    'aiger:rIC3': ('sby', ('sby', 'yosys', 'rIC3'), ('prove', 'bmc')),
    'ebmc': ('ebmc', ('ebmc', 'yosys'), ('prove', 'bmc')),
}


def installed():
    return {name: {'status': 'installed' if all(shutil.which(x) for x in deps) else 'not_installed',
                   'missing': [x for x in deps if not shutil.which(x)], 'modes': list(modes)}
            for name, (_, deps, modes) in ENGINES.items()}


def parse_status(backend, text, returncode, mode):
    if backend == 'sby':
        statuses = set(re.findall(r'^DONE \((PASS|FAIL|UNKNOWN|ERROR)', text, re.M))
        # SBY usually prefixes DONE with time and command name.
        statuses |= set(re.findall(r'\bDONE \((PASS|FAIL|UNKNOWN|ERROR)', text))
        if len(statuses) != 1:
            return 'error'
        verdict = next(iter(statuses))
        expected = {'PASS': 0, 'FAIL': 2, 'UNKNOWN': 4, 'ERROR': 16}
        if returncode != expected[verdict]:
            return 'error'
        if verdict == 'PASS':
            return 'pass' if mode == 'prove' else 'bounded_pass'
        return {'FAIL': 'fail', 'UNKNOWN': 'inconclusive', 'ERROR': 'error'}[verdict]
    if returncode not in (0, 10):
        return 'error'
    try:
        properties = json.loads(text)['properties']
        statuses = [p['status'] for p in properties if p['status'] != 'ASSUMED']
    except (ValueError, KeyError, TypeError):
        return 'error'
    if not statuses:
        return 'inconclusive'
    if any(s == 'REFUTED' or s.startswith('REFUTED up to bound ') for s in statuses):
        return 'fail'
    if all(s == 'PROVED' for s in statuses):
        return 'pass' if mode == 'prove' else 'bounded_pass'
    if all(s == 'PROVED' or s.startswith('PROVED up to bound ') for s in statuses):
        return 'bounded_pass'
    return 'inconclusive'



def race(plan, root, out, *, timeout=30, cross_check=False, yosys_executable=None, smtbmc_logic=None, abc_invariants=False):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    if smtbmc_logic is not None and not re.fullmatch(r'[A-Z0-9_]+', smtbmc_logic):
        raise ValueError('invalid SMTBMC logic name')
    names = plan.get('engines', list(ENGINES))
    if not names or len(names) != len(set(names)) or any(n not in ENGINES for n in names):
        raise ValueError('engines must be unique known engine IDs')
    seed = plan.get('ric3_seed')
    if seed is not None and (type(seed) is not int or not 0 <= seed < 2**64):
        raise ValueError('ric3_seed must be an unsigned 64-bit integer')
    mode = plan.get('mode', 'prove')
    depth = plan.get('depth', 20)
    if mode not in ('bmc', 'prove') or type(depth) is not int or depth < 1:
        raise ValueError('mode must be bmc/prove and depth must be positive')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', plan['top']):
        raise ValueError('invalid top module')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    sources, hashes, transforms = [], [], []
    for i, source in enumerate(plan['sources']):
        data = (Path(root) / source['path']).read_bytes()
        digest = sha256(data).hexdigest()
        if digest != source['sha256']:
            raise ValueError('source hash mismatch')
        if b'`include' in data or b'$readmem' in data:
            raise ValueError('portfolio requires self-contained RTL including memory initial data')
        if source.get('format') == 'aiger':
            from . import aiger_input
            (out / f'input{i}.aig').write_bytes(data)
            data = aiger_input.to_verilog(data, plan['top']).encode()
            transforms.append({'source_sha256': digest, 'verilog_sha256': sha256(data).hexdigest(),
                               'importer_sha256': sha256(Path(aiger_input.__file__).read_bytes()).hexdigest()})
        elif source.get('format', 'verilog') != 'verilog':
            raise ValueError('source format must be verilog or aiger')
        path = out / f'input{i}.sv'
        path.write_bytes(data)
        sources.append(path.resolve())
        hashes.append(digest)
    if any(s.get('format') == 'aiger' for s in plan['sources']) and len(sources) != 1:
        raise ValueError('AIGER input needs exactly one source')
    if not sources:
        raise ValueError('no RTL sources')
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    read_script = 'read -formal ' + ' '.join(p.name for p in sources)
    inventory = installed()
    assumptions = []
    if any(inventory[n]['status'] == 'installed' and mode in ENGINES[n][2] for n in names):
        # Count elaborated safety checks so an empty problem cannot earn a proof.
        script = read_script + '; prep -top ' + plan['top'] + '; write_json design.json'
        check = run_group(['yosys', '-Q', '-T', '-p', script], cwd=out, capture=True, timeout=timeout)
        (out / 'prepare.log').write_text((check.stdout or '') + (check.stderr or ''))
        design = out / 'design.json'
        checks = 0
        if not check.timed_out and check.returncode == 0 and design.exists():
            for module, body in json.loads(design.read_text())['modules'].items():
                for name, cell in body.get('cells', {}).items():
                    flavor = cell.get('parameters', {}).get('FLAVOR')
                    if cell['type'] == '$assert' or (cell['type'] == '$check' and flavor == 'assert'):
                        checks += 1
                    if cell['type'] == '$assume' or (cell['type'] == '$check' and flavor == 'assume'):
                        from .proof_conditions import condition
                        assumptions.append(condition(module, name, cell, out))
        if not checks:
            report = {'schema': 'rvw.formal-portfolio/1', 'status': 'inconclusive',
                      'reason': 'no_checks' if design.exists() and check.returncode == 0 else 'preparation_failed',
                      'rows': [], 'winner': None, 'source_sha256': hashes, 'mode': mode, 'depth': depth}
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            return report
    stopped = threading.Event()
    lock = threading.Lock()
    pids = {}
    cancelled = set()
    rows, winner = [], None
    start = time.monotonic()

    def stop_others(keep=None):
        with lock:
            stopped.set()
            for name, pid in pids.items():
                if name != keep:
                    cancelled.add(name)
                    try:
                        os.killpg(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass

    def run(name):
        backend, dependencies, modes = ENGINES[name]
        row = {'engine': name, **inventory[name], 'wall_s': None}
        if row['status'] == 'not_installed':
            return row
        if mode not in modes:
            return {**row, 'status': 'unsupported_mode'}
        directory = out / name.replace(':', '_')
        directory.mkdir()
        row['tools'] = {d: {'path': shutil.which(d), 'sha256': sha256(Path(shutil.which(d)).read_bytes()).hexdigest()}
                        for d in dependencies}
        if backend == 'sby':
            config = directory / 'problem.sby'
            engine_line = name.replace(':', ' ')
            if name == 'abc:pdr' and abc_invariants:
                engine_line += ' -d'
                row['invariant_export'] = True
            if name.startswith('smtbmc:') and smtbmc_logic is not None:
                engine_line += ' -- --logic ' + smtbmc_logic
                row['smtbmc_logic'] = smtbmc_logic
            if name == 'aiger:rIC3' and seed is not None:
                engine_line += f' --rseed {seed}'
            config.write_text('[options]\nmode ' + mode + f'\ndepth {depth}\n' +
                              '[engines]\n' + engine_line + '\n[script]\n' + read_script + '\nprep -top ' + plan['top'] +
                              '\n[files]\n' + '\n'.join(str(p) for p in sources) + '\n')
            command = ['sby', '-f', 'problem.sby']
            if yosys_executable is not None:
                shim = Path(yosys_executable).resolve()
                command.extend(['--yosys', shlex.quote(str(shim))])
                row['yosys_wrapper_sha256'] = sha256(shim.read_bytes()).hexdigest()
            if name == 'aiger:rIC3' and mode == 'bmc':
                help_result = run_group(['rIC3', '--help'], capture=True, timeout=min(5, timeout))
                if '--end <' in (help_result.stdout or ''):
                    from .ric3_compat import wrapper
                    shim = wrapper(directory, shutil.which('rIC3'))
                    command.extend(['--rIC3', str(shim)])
                    row['compatibility_sha256'] = sha256(shim.read_bytes()).hexdigest()
        else:
            if any(s.get('format') == 'aiger' for s in plan['sources']):
                native_sources = [str((out / 'input0.aig').resolve())]
                top_options = []  # Native AIGER has its own main transition system.
                row['input_format'] = 'aiger_native'
            else:
                native_sources = list(map(str, sources))
                top_options = ['--top', plan['top'], '-D', 'FORMAL', '-D', 'YOSYS']
                row['defines'] = ['FORMAL', 'YOSYS']
            command = ['ebmc', *native_sources, *top_options, '--bound', str(depth), '--json-result', 'ebmc-result.json']
            if mode == 'prove':
                command.append('--k-induction')
        def on_start(pid):
            with lock:
                pids[name] = pid
                if stopped.is_set():
                    cancelled.add(name)
                    os.killpg(pid, signal.SIGTERM)
        began = time.monotonic()
        try:
            proc = run_group(command, cwd=directory, capture=True, timeout=timeout, on_start=on_start)
            text = (proc.stdout or '') + (proc.stderr or '')
            (directory / 'engine.log').write_text(text)
            result_text = text
            if backend == 'ebmc':
                result_file = directory / 'ebmc-result.json'
                result_text = result_file.read_text() if result_file.exists() else ''
            status = 'timeout' if proc.timed_out else parse_status(backend, result_text, proc.returncode, mode)
            with lock:
                pids.pop(name, None)
                if name in cancelled:
                    status = 'cancelled'
            from .engine_limits import avy_failure
            diagnostic = avy_failure(directory, text) if name == 'aiger:avy' and status == 'error' else {}
            return {**row, **diagnostic, 'status': status, 'wall_s': time.monotonic() - began,
                    'returncode': proc.returncode, 'command': command}
        except OSError as exc:
            with lock:
                pids.pop(name, None)
            return {**row, 'status': 'error', 'reason': str(exc), 'wall_s': time.monotonic() - began}

    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        futures = [pool.submit(run, name) for name in names]
        try:
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                if winner is None and row['status'] in ('pass', 'fail'):
                    winner = {'engine': row['engine'], 'status': row['status'], 'time_to_result_s': time.monotonic() - start}
                    if not cross_check:
                        stop_others(row['engine'])
        finally:
            stop_others()
    decisive = [r for r in rows if r['status'] in ('pass', 'fail')]
    disagreement = len({r['status'] for r in decisive}) > 1
    uncertified_environment = bool(assumptions) and winner and winner['status'] == 'pass'
    report = {'schema': 'rvw.formal-portfolio/1', 'status': 'inconclusive' if disagreement or not winner or uncertified_environment else winner['status'],
              'environment_check': 'activation_not_checked' if assumptions else 'no_source_assumptions',
              'winner': winner, 'cross_check': 'disagree' if disagreement else 'agree' if len(decisive) > 1 else 'inconclusive',
              'proof_kind': 'unbounded' if winner and winner['status'] == 'pass' and not disagreement and not uncertified_environment else 'none',
              'rows': rows, 'assumptions': assumptions,
              'condition_model': {'path': 'design.json', 'sha256': sha256((out / 'design.json').read_bytes()).hexdigest()} if (out / 'design.json').exists() else None, 'source_transforms': transforms, 'source_sha256': hashes, 'mode': mode, 'depth': depth,
              'limits': 'Source assertions and assumptions define the problem. No reset, clock, or vacuity guards are added. '
                        'Proofs are conditional on source assumptions. Cancelled or absent answers cannot be cross-checked.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
