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


def prepare(pack, source, out, task):
    source, out = Path(source).resolve(), Path(out).resolve()
    revision = git(source, 'rev-parse', 'HEAD')
    if revision != pack['source']['revision']:
        raise ValueError(f'source revision {revision} differs from the task pin')
    if git(source, 'status', '--porcelain', '--', *pack['source']['copy']):
        raise ValueError('source inputs are dirty')
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
    argv = ['nice', '-n', '10', str(adapter), 'run-many', '--manifest', str(manifest), '--jobs', '1',
            '--config', pack['config'], '--seed', str(pack.get('seed', 1)), '--rvfi-trace',
            *pack.get('run_args', [])]
    proc = run_group(argv, env=environment(pack, workspace), timeout=timeout, capture=True)
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
                      'trace': str(trace), 'exit_code': proc.returncode, 'timed_out': proc.timed_out}
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


def qualify(pack_path, source, out, *, task_ids=None, timeout=110):
    pack, digest, base = load_pack(pack_path)
    tasks = [t for t in pack['tasks'] if task_ids is None or t['id'] in task_ids]
    if not tasks or (task_ids and set(task_ids) != {t['id'] for t in tasks}):
        raise ValueError('unknown task ID')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'rvw.agent-native-qualification/1', 'track': 'native', 'pack_sha256': digest,
              'source_revision': pack['source']['revision'], 'workstation_revision': git(HOME, 'rev-parse', 'HEAD'),
              'tasks': [], 'automatic_root_cause': 'NOT CLAIMED', 'c4_acceptance': 'NOT CLAIMED'}
    for task in tasks:
        root = out / task['id']
        workspace = prepare(pack, source, root / 'workspace', task)
        tests = task['private']['fail_to_pass'] + task['private']['pass_to_pass']
        seeded = run_tests(pack, base, workspace, root / 'seeded', tests, timeout)
        if any(r['status'] not in ('pass', 'fail', 'assert', 'rvfi_error') for r in seeded.values()):
            report['tasks'].append({'id': task['id'], 'status': 'inconclusive', 'seeded': seeded,
                                    'repaired': {}, 'reason': 'seeded workload evidence is incomplete'})
            (out / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
            continue
        mutate(workspace, task['private']['mutation'], reverse=True)
        git(workspace, 'add', '-A')
        git(workspace, 'commit', '-qm', 'repair task')
        repaired = run_tests(pack, base, workspace, root / 'repaired', tests, timeout)
        report['tasks'].append({'id': task['id'], 'status': qualification(task, seeded, repaired),
                                'seeded': seeded, 'repaired': repaired})
        (out / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
