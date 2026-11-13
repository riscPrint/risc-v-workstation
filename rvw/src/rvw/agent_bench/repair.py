"""A native repair loop with an evaluator-owned failure and independent workload checks."""
import hashlib
import json
import shutil
import sys

from rvw.common.proc import run_group
from pathlib import Path

from . import native


def prepare_challenge(pack_path, task_id, source, out, *, timeout=110):
    pack, digest, base = native.load_pack(pack_path)
    task = next((t for t in pack['tasks'] if t['id'] == task_id), None)
    if task is None:
        raise ValueError('unknown task ID')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    workspace = native.prepare(pack, source, out / 'workspace', task)
    for item in pack.get('project_copy', []):
        src, dst = base / item['source'], workspace / item['dest']
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('target', 'out', '.bloop', '.metals', 'simWorkspace'))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for mutation in pack.get('project_mutations', []):
        native.mutate(workspace, mutation)
    for item in pack.get('program_copy', []):
        shutil.copytree(base / item['source'], workspace / item['dest'])
    (workspace / 'TASK.md').write_text(task['public']['summary'] + '\n\n'
        + 'Failing programs: ' + ', '.join(task['public']['failing']) + '.\n'
        + 'Use rvw agent guide --workflow test-fails --json. Change only core source files.\n'
        + 'Check result identities before using evidence. Do not edit tests or the adapter.\n')
    native.git(workspace, 'add', '-A')
    native.git(workspace, 'commit', '-qm', 'project inputs', '--allow-empty')
    baseline = native.git(workspace, 'rev-parse', 'HEAD')
    truth = task['private']
    tests = truth['fail_to_pass'] + truth['pass_to_pass']
    seeded = native.run_tests(pack, base, workspace, out / 'seeded', tests, timeout)
    reproduced = (all(seeded[n]['status'] in ('fail', 'assert', 'rvfi_error') for n in truth['fail_to_pass'])
                  and all(seeded[n]['status'] == 'pass' for n in truth['pass_to_pass']))
    diagnostics = {}
    if reproduced:
        for name in truth['fail_to_pass']:
            diagnostics[name] = {}
            for command, arguments in (
                ('bundle', ['bundle', str(Path(seeded[name]['result']).parent), '--out', str(out / 'bundles' / name),
                            '--no-rerun', '--no-spinaltrace', '--json']),
                ('cosim', ['cosim', 'check', '--trace', seeded[name]['trace'], '--elf', str((base / pack['programs'] / name).resolve()), '--json'])):
                proc = run_group([sys.executable, '-m', 'rvw', '--project', str(workspace), *arguments],
                                 env=native.environment(pack, workspace), timeout=30, capture=True)
                path = out / f'{name}-{command}.json'
                path.write_text(proc.stdout or '{}')
                (out / f'{name}-{command}.log').write_text(proc.stderr or '')
                diagnostics[name][command] = {'exit_code': proc.returncode, 'timed_out': proc.timed_out,
                                              'result': str(path)}
    state = {'schema': 'rvw.agent-repair-challenge/1', 'pack': str(Path(pack_path).resolve()),
             'pack_sha256': digest, 'source': str(Path(source).resolve()), 'task': task_id,
             'workspace': str(workspace), 'baseline': baseline, 'seeded': seeded,
             'reproduced': reproduced, 'diagnostics': diagnostics, 'status': 'ready' if reproduced else 'inconclusive'}
    (out / 'challenge.json').write_text(json.dumps(state, indent=2) + '\n')
    return state


def check_challenge(challenge, out, *, timeout=110):
    state = json.loads(Path(challenge).read_text())
    pack, digest, base = native.load_pack(state['pack'])
    if digest != state['pack_sha256']:
        raise ValueError('task pack changed since failure reproduction')
    task = next(t for t in pack['tasks'] if t['id'] == state['task'])
    workspace = Path(state['workspace'])
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    changes = native.git(workspace, 'diff', '--name-only', state['baseline']).splitlines()
    changes += native.git(workspace, 'ls-files', '--others', '--exclude-standard').splitlines()
    prefixes = tuple(name.rstrip('/') + '/' for name in pack['source']['copy'])
    sources = sorted({name for name in changes if name.startswith(prefixes)})
    ignored = sorted(set(changes) - set(sources) - {'TASK.md'})
    clean = native.prepare(pack, state['source'], out / 'check-workspace', task)
    for name in sources:
        src, dst = workspace / name, clean / name
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        elif dst.exists():
            dst.unlink()
    native.git(clean, 'add', '-A')
    native.git(clean, 'commit', '-qm', 'candidate sources', '--allow-empty')
    patch = native.git(clean, 'diff', 'HEAD~1', 'HEAD')
    (out / 'candidate.patch').write_text(patch + '\n')
    tests = task['private']['fail_to_pass'] + task['private']['pass_to_pass']
    repaired = native.run_tests(pack, base, clean, out / 'repaired', tests, timeout)
    verdict = native.qualification(task, state['seeded'], repaired) if state['reproduced'] else 'inconclusive'
    report = {'schema': 'rvw.agent-repair-check/1', 'task': state['task'], 'pack_sha256': digest,
              'status': {'qualified': 'repair_verified', 'unqualified': 'repair_rejected'}.get(verdict, verdict),
              'reproduced': state['reproduced'], 'source_files': sources, 'ignored_files': ignored,
              'candidate_patch_sha256': hashlib.sha256((out / 'candidate.patch').read_bytes()).hexdigest(),
              'seeded': state['seeded'], 'repaired': repaired, 'root_cause': 'unknown: no dynamic statement join',
              'c4_acceptance': 'NOT CLAIMED', 'human_review': 'required'}
    (out / 'repair.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
