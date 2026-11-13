"""Head-to-head debug task protocol: fixed questions, an rvw answer, a reference tool's answer.

A task file (`rvw.debug-tasks/1`) lists tasks. Each has a `question`, the `argv` of one rvw
command (with `{name}` variables), `expect` checks on its JSON output, and an optional
`reference` record for another tool (for example Verdi): `tool`, `seconds`, `steps`, `solved`,
`notes`, filled in by the person who ran it. `rvw wave bench` runs the rvw side, times it and
checks the answer. A comparison is reported only for tasks with a recorded reference.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from .vcd import WaveError

SCHEMA = 'rvw.debug-tasks/1'


def _get(data, path: str):
    node = data
    for part in path.split('.') if path else []:
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return _MISSING
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return _MISSING
    return node


_MISSING = object()


def _check(data, e: dict) -> dict:
    got = _get(data, e['path'])
    if 'equals' in e:
        ok = got is not _MISSING and got == e['equals']
    elif 'contains' in e:
        ok = got is not _MISSING and e['contains'] in (got if isinstance(got, (list, str)) else json.dumps(got))
    elif 'any' in e:
        # `any`: some element of the list at `path` has all the given fields.
        ok = isinstance(got, list) and any(isinstance(x, dict) and all(x.get(k) == v for k, v in e['any'].items())
                                           for x in got)
    else:
        raise WaveError(f'expectation needs equals, contains or any: {e}')
    return {**e, 'ok': ok, 'got': None if got is _MISSING else got if not isinstance(got, (dict, list)) else '...'}


def run(path: str, variables: dict[str, str] | None = None, only: list[str] | None = None,
        timeout: float = 600) -> dict:
    try:
        spec = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise WaveError(f'cannot read task file {path}: {exc}') from exc
    if spec.get('schema') != SCHEMA:
        raise WaveError(f'unsupported task schema: {spec.get("schema")}')
    base = Path(path).absolute().parent
    values = {'dir': str(base), **(spec.get('defaults') or {}), **(variables or {})}
    rows = []
    for task in spec.get('tasks') or []:
        if only and task['id'] not in only:
            continue
        try:
            argv = [str(a).format(**values) for a in task['argv']]
        except KeyError as exc:
            rows.append({'id': task['id'], 'status': 'error', 'cause': f'missing variable {exc}; pass --var'})
            continue
        start = time.perf_counter()
        try:
            p = subprocess.run([sys.executable, '-m', 'rvw', *argv, '--json'], cwd=base, capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            rows.append({'id': task['id'], 'status': 'error', 'cause': f'timeout after {timeout} s'})
            continue
        seconds = time.perf_counter() - start
        try:
            data = json.loads(p.stdout)
        except ValueError:
            rows.append({'id': task['id'], 'status': 'error', 'seconds': seconds,
                         'cause': (p.stderr or 'no JSON output').strip()[-400:]})
            continue
        checks = [_check(data, e) for e in task.get('expect') or []]
        status = 'solved' if checks and all(c['ok'] for c in checks) else 'unsolved' if checks else 'no_checks'
        row = {'id': task['id'], 'question': task.get('question'), 'status': status, 'seconds': round(seconds, 3),
               'exit': p.returncode, 'checks': checks}
        ref = task.get('reference') or {}
        if ref.get('seconds') is not None:
            row['reference'] = ref
            row['speedup'] = round(ref['seconds'] / seconds, 2) if seconds and status == 'solved' else None
        rows.append(row)
    solved = [r for r in rows if r['status'] == 'solved']
    compared = [r for r in rows if 'reference' in r]
    return {'tasks': path, 'results': rows, 'solved': len(solved), 'total': len(rows),
            'rvw_seconds': round(sum(r.get('seconds', 0) for r in rows), 3),
            'compared': len(compared),
            'comparison': ('no reference results recorded; nothing is compared' if not compared else
                           f'{len(compared)} tasks with recorded reference results'),
            'basis': 'rvw wall time per command on this machine; reference times are recorded by hand and '
                     'include human steps; a solved task means its expectations held, not that the tools are equal'}
