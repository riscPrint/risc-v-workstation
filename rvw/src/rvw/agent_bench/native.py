"""Project-owned seeded mutations and independent C1 repair checks.

Core names, signal names, test lists and adapter paths belong in task packs.
This module never patches a source checkout. Each task uses a disposable copy.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rvw.common.proc import run_group
from rvw.cosim.trace import Trace

SCHEMA = 'rvw.agent-native-tasks/1'
HOME = Path(__file__).resolve().parents[4]


def load_pack(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    pack = json.loads(raw)
    if pack.get('schema') != SCHEMA or not pack.get('tasks'):
        raise ValueError(f'expected {SCHEMA}')
    ids = [t['id'] for t in pack['tasks']]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate task IDs')
    for task in pack['tasks']:
        if not task['private']['fail_to_pass'] or not task['private']['pass_to_pass']:
            raise ValueError('each task needs fail-to-pass and pass-to-pass tests')
    return pack, hashlib.sha256(raw).hexdigest(), path.parent


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, text=True, capture_output=True,
                          env={**os.environ, 'GIT_AUTHOR_NAME': 'rvw-bench', 'GIT_AUTHOR_EMAIL': 'bench@example.invalid',
                               'GIT_COMMITTER_NAME': 'rvw-bench', 'GIT_COMMITTER_EMAIL': 'bench@example.invalid'}).stdout.strip()


def mutate(root, mutation, reverse=False):
    path = Path(root) / mutation['file']
    old, new = mutation['find'], mutation['replace']
    if reverse:
        old, new = new, old
    text = path.read_text()
    occurrence = 1 if reverse else mutation.get('occurrence', 1)
    index = -1
    for _ in range(occurrence):
        index = text.find(old, index + 1)
        if index < 0:
            raise ValueError(f'{path}: mutation text not found')
    path.write_text(text[:index] + new + text[index + len(old):])


def verify_source(pack, source):
    source = Path(source).resolve()
    revision = git(source, 'rev-parse', 'HEAD')
    if revision != pack['source']['revision']:
        raise ValueError(f'source revision {revision} differs from the task pin')
    if git(source, 'status', '--porcelain', '--', *pack['source']['copy']):
        raise ValueError('source inputs are dirty')
    return source


def verify_workspace(pack, source, workspace):
    source = verify_source(pack, source)
    workspace = Path(workspace).resolve()
    if workspace == source:
        raise ValueError('reuse cannot use the original source checkout')
    expected = {name for name in git(source, 'ls-files', '--', *pack['source']['copy']).splitlines()
                if (source / name).is_file()}
    actual = set(git(workspace, 'ls-files').splitlines())
    if not expected or not actual or actual - expected or git(workspace, 'status', '--porcelain', '--', *pack['source']['copy']):
        raise ValueError('reused workspace is not a clean pinned source copy')
    if any(not (workspace / name).is_file() or (workspace / name).is_symlink()
           or not (workspace / name).resolve().is_relative_to(workspace)
           or (source / name).read_bytes() != (workspace / name).read_bytes() for name in expected):
        raise ValueError('reused workspace differs from the pinned source')


def prepare(pack, source, out, task):
    source, out = verify_source(pack, source), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    for name in pack['source']['copy']:
        shutil.copytree(source / name, out / name)
    mutate(out, task['private']['mutation'])
    git(out, 'init', '-q')
    git(out, 'add', '-A')
    git(out, 'commit', '-qm', 'seed task')
    return out


def environment(pack, workspace):
    env = {k: v for k, v in os.environ.items() if k not in ('RVW_PROJECT', 'RVW_CORE', 'RVW_CORE_SOURCE')}
    env.update(RVW_HOME=str(HOME), RVW_PYTHON=sys.executable, RVW_LOCK_PYTHON=sys.executable)
    env.update(pack.get('environment', {}))
    env[pack['source']['env']] = str(Path(workspace).resolve())
    return env


def run_tests(pack, base, workspace, out, tests, timeout):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    adapter = (base / pack['adapter']).resolve()
    programs = (base / pack['programs']).resolve()
    manifest = out / 'jobs.jsonl'
    manifest.write_text(''.join(json.dumps({'elf': str(programs / name), 'out': str(out / name)}) + '\n'
                                for name in tests))
    argv = ['nice', '-n', str(pack.get('nice', 15)), str(adapter), 'run-many', '--manifest', str(manifest), '--jobs', '1',
            '--config', pack['config'], '--seed', str(pack.get('seed', 1)), '--rvfi-trace',
            *pack.get('run_args', [])]
    started = time.monotonic()
    proc = run_group(argv, env=environment(pack, workspace), timeout=timeout, capture=True)
    elapsed = time.monotonic() - started
    (out / 'adapter.log').write_text((proc.stdout or '') + (proc.stderr or ''))
    runs = {}
    for name in tests:
        run_dir = out / name
        try:
            result = json.loads((run_dir / 'result.json').read_text())
        except (OSError, ValueError):
            result = {}
        # A status string alone cannot qualify a native task.
        identity = {k: result.get(k) for k in ('rtl_sha256', 'elf_sha256', 'seed', 'config', 'source')}
        trace = run_dir / 'rvfi.jsonl'
        end = None
        valid_trace = False
        try:
            capture = Trace(trace)
            retired = 0
            for row in capture:
                if row.get('event') == 'end':
                    end = row
                elif 'event' not in row:
                    retired += 1
            valid_trace = retired > 0 and all(capture.header.get(k) == identity[k]
                                            for k in ('rtl_sha256', 'elf_sha256', 'seed', 'config', 'source'))
        except (OSError, ValueError):
            pass
        status = result.get('status', 'inconclusive')
        hashes = all(isinstance(identity[k], str) and len(identity[k]) == 64 for k in ('rtl_sha256', 'elf_sha256'))
        expected_elf = hashlib.sha256((programs / name).read_bytes()).hexdigest()
        source = identity.get('source') or {}
        if (proc.timed_out or not hashes or not valid_trace or not end or end.get('status') != status
                or identity['elf_sha256'] != expected_elf or not source.get('core_rev')):
            status = 'inconclusive'
        runs[name] = {'status': status, 'identity': identity, 'result': str(run_dir / 'result.json'),
                      'trace': str(trace), 'batch_wall_s': elapsed,
                      'trace_complete': bool(valid_trace and end and end.get('status') == result.get('status')), 'exit_code': proc.returncode, 'timed_out': proc.timed_out}
    return runs


def qualification(task, seeded, repaired):
    truth = task['private']
    expected = set(truth['fail_to_pass'] + truth['pass_to_pass'])
    if set(seeded) != expected or set(repaired) != expected:
        return 'inconclusive'
    if any(r['status'] not in ('pass', 'fail', 'assert', 'rvfi_error') for r in [*seeded.values(), *repaired.values()]):
        return 'inconclusive'
    if any(seeded[n]['status'] not in ('fail', 'assert', 'rvfi_error') for n in truth['fail_to_pass']):
        return 'unqualified'
    if any(seeded[n]['status'] != 'pass' for n in truth['pass_to_pass']) or any(r['status'] != 'pass' for r in repaired.values()):
        return 'unqualified'
    for name in expected:
        a, b = seeded[name]['identity'], repaired[name]['identity']
        if not a.get('rtl_sha256') or a['rtl_sha256'] == b.get('rtl_sha256'):
            return 'inconclusive'
        a_tools = (a.get('source') or {}).get('tools_rev')
        b_tools = (b.get('source') or {}).get('tools_rev')
        if not a_tools or a_tools != b_tools:
            return 'inconclusive'
        if a.get('elf_sha256') != b.get('elf_sha256') or a.get('seed') != b.get('seed') or a.get('config') != b.get('config'):
            return 'inconclusive'
    return 'qualified'


def reference_checks(pack, base, workspace, runs, timeout):
    """Retain strict Spike output, including failures to launch the reference."""
    for name, run in runs.items():
        started = time.monotonic()
        argv = [sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', 'native-task',
                '--trace', run['trace'], '--elf', str((base / pack['programs'] / name).resolve()),
                '--platform', str((base / pack['platform']).resolve()), '--strict', '--json']
        proc = run_group(argv, env=environment(pack, workspace), timeout=timeout, capture=True)
        destination = Path(run['result']).parent.parent / (name + '-cosim.json')
        destination.write_text(proc.stdout or '{}')
        destination.with_suffix('.log').write_text(proc.stderr or '')
        try:
            result = json.loads(proc.stdout or '{}')
        except ValueError:
            result = {}
        expected_code = {'match': 0, 'mismatch': 1}.get(result.get('status'))
        run['cosim'] = {'status': result.get('status', 'inconclusive')
                        if not proc.timed_out and expected_code == proc.returncode else 'inconclusive',
                        'mismatch': result.get('mismatch'), 'wall_s': time.monotonic() - started,
                        'exit_code': proc.returncode, 'timed_out': proc.timed_out, 'result': str(destination)}


def native_verdict(task, baseline, seeded, repaired):
    # A complete cycle-limit run with a real architectural mismatch detects a seed.
    # A wall timeout or a matching prefix cannot do so. Preserve raw C1 status.
    evaluated = dict(seeded)
    for name in task['private']['fail_to_pass']:
        run = seeded.get(name, {})
        if (run.get('status') == 'timeout' and run.get('trace_complete')
                and not run.get('timed_out') and run.get('cosim', {}).get('status') == 'mismatch'
                and run['cosim'].get('mismatch')):
            evaluated[name] = {**run, 'status': 'fail'}
    verdict = qualification(task, evaluated, repaired)
    if verdict != 'qualified':
        return verdict
    if set(baseline) != set(seeded):
        return 'inconclusive'
    for name, run in baseline.items():
        if run['status'] != 'pass' or run.get('cosim', {}).get('status') != 'match':
            return 'inconclusive'
        a, b = run['identity'], repaired[name]['identity']
        if any(a.get(k) != b.get(k) for k in ('elf_sha256', 'seed', 'config')):
            return 'inconclusive'
        if (a.get('source') or {}).get('tools_rev') != (b.get('source') or {}).get('tools_rev'):
            return 'inconclusive'
    for name in seeded:
        expected = 'mismatch' if name in task['private']['fail_to_pass'] else 'match'
        check = seeded[name].get('cosim', {})
        if check.get('status') != expected or (expected == 'mismatch' and not check.get('mismatch')):
            return 'inconclusive'
        if repaired[name].get('cosim', {}).get('status') != 'match':
            return 'inconclusive'
    return 'qualified'


def qualify(pack_path, source, out, *, task_ids=None, timeout=110, reuse_workspace=False):
    pack, digest, base = load_pack(pack_path)
    tasks = [t for t in pack['tasks'] if task_ids is None or t['id'] in task_ids]
    if not tasks or (task_ids and set(task_ids) != {t['id'] for t in tasks}):
        raise ValueError('unknown task ID')
    out = Path(out).resolve()
    attempt, previous = 1, None
    if reuse_workspace:
        if not out.is_dir():
            raise ValueError('reuse needs an existing qualification directory')
        verify_workspace(pack, source, out / 'workspace')
        previous_path = out / 'qualification.json'
        if previous_path.exists():
            previous = json.loads(previous_path.read_text())
            attempt = previous.get('attempt', 1) + 1
        else:
            attempt = 2
        while (out / f'attempt-{attempt}').exists():
            attempt += 1
        phase = out / f'attempt-{attempt}'
        phase.mkdir()
        if previous is not None:
            archive = out / f'qualification-attempt-{attempt-1}.json'
            with archive.open('x') as stream:
                stream.write(json.dumps(previous, indent=2) + '\n')
    else:
        out.mkdir(parents=True, exist_ok=False)
        phase = out
    report = {'schema': 'rvw.agent-native-qualification/1', 'track': 'native', 'pack_sha256': digest,
              'source_revision': pack['source']['revision'], 'workstation_revision': git(HOME, 'rev-parse', 'HEAD'),
              'attempt': attempt, 'previous_pack_sha256': previous.get('pack_sha256') if previous else None,
              'tasks': [], 'automatic_root_cause': 'NOT CLAIMED', 'c4_acceptance': 'NOT CLAIMED'}
    # One stable source path lets sbt reuse unchanged core classes between tasks.
    workspace = out / 'workspace'
    if not reuse_workspace:
        workspace = prepare(pack, source, workspace, tasks[0])
        mutate(workspace, tasks[0]['private']['mutation'], reverse=True)
        git(workspace, 'add', '-A')
        git(workspace, 'commit', '-qm', 'baseline task')
    all_tests = list(dict.fromkeys(name for task in tasks for name in
                                  task['private']['fail_to_pass'] + task['private']['pass_to_pass']))
    baseline = run_tests(pack, base, workspace, phase / 'baseline', all_tests, timeout)
    if all(r['status'] == 'pass' for r in baseline.values()):
        if 'platform' not in pack:
            raise ValueError('native qualification requires a Spike platform in the task pack')
        reference_checks(pack, base, workspace, baseline, min(timeout, 30))
    for task in tasks:
        root = phase / task['id']
        tests = task['private']['fail_to_pass'] + task['private']['pass_to_pass']
        control = {name: baseline[name] for name in tests}
        if any(r['status'] != 'pass' or r.get('cosim', {}).get('status') != 'match' for r in control.values()):
            report['tasks'].append({'id': task['id'], 'status': 'inconclusive', 'baseline': control,
                                    'seeded': {}, 'repaired': {}, 'reason': 'baseline did not pass and match'})
        else:
            mutate(workspace, task['private']['mutation'])
            git(workspace, 'add', '-A')
            git(workspace, 'commit', '-qm', 'seed ' + task['id'])
            try:
                seeded = run_tests(pack, base, workspace, root / 'seeded', tests, timeout)
            finally:
                mutate(workspace, task['private']['mutation'], reverse=True)
                git(workspace, 'add', '-A')
                git(workspace, 'commit', '-qm', 'repair ' + task['id'])
            if any(r['status'] not in ('pass', 'fail', 'assert', 'rvfi_error', 'timeout') for r in seeded.values()):
                report['tasks'].append({'id': task['id'], 'status': 'inconclusive', 'baseline': control,
                                        'seeded': seeded, 'repaired': {},
                                        'reason': 'seeded workload evidence is incomplete'})
            else:
                repaired = run_tests(pack, base, workspace, root / 'repaired', tests, timeout)
                reference_checks(pack, base, workspace, seeded, min(timeout, 30))
                reference_checks(pack, base, workspace, repaired, min(timeout, 30))
                report['tasks'].append({'id': task['id'], 'baseline': control,
                                        'status': native_verdict(task, control, seeded, repaired),
                                        'seeded': seeded, 'repaired': repaired})
        (out / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
