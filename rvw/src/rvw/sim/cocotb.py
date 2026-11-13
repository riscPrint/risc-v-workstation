"""Native cocotb component runs. No ELF, cache or gate acceptance claims."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

from rvw.common.proc import run_group
from rvw.results import write_json
from rvw.sim.backends import require


def load(path: Path) -> dict:
    path = path.resolve(strict=True)
    data = json.loads(path.read_text())
    allowed = {'schema', 'name', 'backend', 'top', 'sources', 'test_module',
               'python_paths', 'requires', 'clock', 'reset', 'data_files'}
    if not isinstance(data, dict) or set(data) - allowed or data.get('schema') != 'rvw.cocotb/1':
        raise ValueError('invalid cocotb manifest schema or fields')
    for key in ('name', 'top', 'test_module'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    for key in ('sources', 'python_paths', 'requires', 'data_files'):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
            raise ValueError(f'{key} must be a string list')
    require(data.get('backend'), data.get('requires', []))
    if not data.get('sources'):
        raise ValueError('sources must not be empty')
    for key in ('sources', 'python_paths', 'data_files'):
        data[key] = [str((path.parent / p).resolve(strict=True)) for p in data.get(key, [])]
    names=[Path(p).name for p in data['data_files']]
    if len(names)!=len(set(names)):
        raise ValueError('data_files must have distinct basenames')
    clock = data.get('clock')
    if clock is not None:
        if (not isinstance(clock, dict) or set(clock) != {'signal', 'period_ns'}
                or not isinstance(clock['signal'], str) or not clock['signal']
                or type(clock['period_ns']) not in (int, float)
                or not math.isfinite(clock['period_ns']) or clock['period_ns'] <= 0):
            raise ValueError('clock needs signal and positive finite period_ns')
        require(data['backend'], ['clock', 'timer'])
    reset = data.get('reset')
    if reset is not None:
        if (not clock or not isinstance(reset, dict) or set(reset) != {'signal', 'active', 'cycles'}
                or not isinstance(reset['signal'], str) or not reset['signal']
                or type(reset['active']) is not int or reset['active'] not in (0, 1)
                or type(reset['cycles']) is not int or reset['cycles'] < 1):
            raise ValueError('reset needs a clock, signal, active (0/1) and positive cycles')
    return data


def entries(xml: Path, seed: int) -> list[dict]:
    cases = list(ET.parse(xml).getroot().iter('testcase'))
    if not cases:
        raise ValueError('cocotb produced no test cases')
    rows = []
    seen = set()
    for index, case in enumerate(cases):
        failed = case.find('failure') is not None
        error = case.find('error') is not None
        skipped = case.find('skipped') is not None
        status = 'error' if error or skipped else 'fail' if failed else 'pass'
        row = {'id': f"{case.get('classname', '')}.{case.get('name', index)}",
               'status': status, 'seed': seed, 'kind': 'cocotb',
               'signature': None if status == 'pass' else f'cocotb:{status}',
               'wall_s': float(case.get('time', 0))}
        if row['id'] in seen or not math.isfinite(row['wall_s']) or row['wall_s'] < 0:
            raise ValueError('duplicate test identity or invalid duration in cocotb XML')
        seen.add(row['id'])
        detail = case.find('failure') if failed else case.find('error')
        if detail is not None:
            row['message'] = detail.get('message') or detail.text or 'cocotb test failed'
        if skipped:
            row['inconclusive'] = 'cocotb skipped this test'
        rows.append(row)
    return rows


def run(manifest: Path, out: Path, *, seed=1, timeout=120) -> dict:
    data = load(manifest)  # Refuse capabilities before creating output or spawning tools.
    if type(seed) is not int or seed < 0:
        raise ValueError('seed must be a nonnegative integer')
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be positive and finite')
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)  # No stale XML or reuse.
    write_json(out / 'request.json', data)
    inputs = {str(manifest.resolve()): hashlib.sha256(manifest.read_bytes()).hexdigest()}
    paths = [*data['sources'], *data['data_files']]
    for directory in data['python_paths']:
        paths.extend(str(p) for p in Path(directory).rglob('*.py'))
    for path in paths:
        inputs[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    start = time.monotonic()
    with (out / 'run.log').open('w') as log:
        result = run_group([sys.executable, '-m', 'rvw.sim.worker', str(out), str(seed)],
                           timeout=timeout, stdout=log, stderr=log)
    try:
        rows = entries(out / 'cocotb.xml', seed)
        if result.returncode and all(row['status'] == 'pass' for row in rows):
            raise ValueError(f'worker exited {result.returncode} after passing XML')
        if result.timed_out:
            raise ValueError('wall-clock timeout')
    except (OSError, ValueError, ET.ParseError) as exc:
        rows = [{'id': data['name'], 'status': 'error', 'seed': seed, 'kind': 'cocotb',
                 'signature': 'cocotb:error', 'inconclusive': str(exc)}]
    changed = [path for path, digest in inputs.items()
               if not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest]
    if changed:
        for row in rows:
            row['status'] = 'error'
            row['signature'] = 'cocotb:inputs_changed'
            row['inconclusive'] = 'inputs changed during the run'
    for row in rows:
        row['artifacts'] = {'log': 'run.log', 'request': 'request.json'}
        if (out / 'cocotb.xml').exists():
            row['artifacts']['junit'] = 'cocotb.xml'
    report = {'schema': 'rvw.results/1', 'run_id': out.name, 'suite': data['name'],
              'core': data['top'], 'config': data['backend'],
              'created': dt.datetime.now(dt.timezone.utc).isoformat(),
              'source': {'input_sha256': inputs}, 'tests': rows,
              'backend': require(data['backend']).to_dict(), 'seed': seed,
              'wall_s': time.monotonic() - start,
              'timeout_s': timeout,
              'artifacts': {'log': 'run.log', 'request': 'request.json'},
              'replay': [sys.executable, '-m', 'rvw', 'regress', 'cocotb',
                         str(manifest.resolve()), '--seed', str(seed), '--timeout', str(timeout), '--out', '<new-directory>']}
    write_json(out / 'results.json', report)
    return report
