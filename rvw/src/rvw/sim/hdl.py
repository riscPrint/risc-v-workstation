"""Native HDL component tests with explicit semantic profiles."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time

from rvw.common.proc import run_group
from rvw.results import write_json
from rvw.sim.backends import BACKENDS

PROFILES = {
    'icarus': replace(BACKENDS['icarus'], scheduling='event-driven HDL testbench',
                      features=BACKENDS['icarus'].features + ('hdl_delays',)),
    'verilator-timing': replace(
        BACKENDS['verilator'], scheduling='compiled HDL events with --timing',
        features=BACKENDS['verilator'].features + ('hdl_delays', 'fork_join')),
    'ghdl-yosys-icarus': replace(
        BACKENDS['icarus'], languages=('synthesizable VHDL-2008', 'SystemVerilog subset'),
        x_handling='VHDL synthesis can change unknowns; no VHDL X guarantee',
        scheduling='Icarus events on GHDL/Yosys synthesized VHDL netlist',
        foreign=(), features=('mixed_synth', 'hdl_delays', 'immediate_assertions')),
}
TOOLS = {'icarus': ('iverilog', 'vvp'),
         'verilator-timing': ('verilator', 'make', 'c++'),
         'ghdl-yosys-icarus': ('ghdl', 'yosys', 'iverilog', 'vvp')}
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


def require(backend, features):
    if backend not in PROFILES:
        raise ValueError(f'unsupported HDL backend: {backend}')
    missing = set(features) - set(PROFILES[backend].features)
    if missing:
        raise ValueError(f'{backend} cannot provide required features: {", ".join(sorted(missing))}')
    return PROFILES[backend]


def load(manifest: Path, backend=None):
    manifest = manifest.resolve(strict=True)
    data = json.loads(manifest.read_text())
    allowed = {'schema', 'backend', 'top', 'sources', 'requires', 'vhdl_sources', 'vhdl_top'}
    if not isinstance(data, dict) or set(data) - allowed or data.get('schema') != 'rvw.hdl/1':
        raise ValueError('invalid HDL manifest schema or fields')
    if backend is not None:
        data['backend'] = backend
    if not isinstance(data.get('backend'), str):
        raise ValueError('backend must be a string')
    for key in ('requires', 'sources', 'vhdl_sources'):
        value = data.setdefault(key, [])
        if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
            raise ValueError(f'{key} must be a string list')
    require(data['backend'], data['requires'])
    for key in ('top', 'vhdl_top'):
        if key == 'top' or key in data:
            if not isinstance(data.get(key), str) or not IDENT.fullmatch(data[key]):
                raise ValueError(f'{key} must be a simple HDL identifier')
    mixed = data['backend'] == 'ghdl-yosys-icarus'
    if mixed != bool(data['vhdl_sources']) or mixed != bool(data.get('vhdl_top')):
        raise ValueError('VHDL sources and vhdl_top require the mixed synthesis profile')
    if not data['sources']:
        raise ValueError('sources must not be empty')
    for key in ('sources', 'vhdl_sources'):
        data[key] = [str((manifest.parent / p).resolve(strict=True)) for p in data[key]]
        if not all(Path(p).is_file() for p in data[key]):
            raise ValueError('sources must be files')
    return data


def run(manifest: Path, out: Path, *, backend=None, timeout=120):
    data = load(manifest, backend)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be positive and finite')
    paths = {}
    for tool in TOOLS[data['backend']]:
        paths[tool] = shutil.which(tool)
        if not paths[tool]:
            raise ValueError(f'missing native tool: {tool}')
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'request.json', data)
    inputs = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [manifest.resolve(), *(Path(s) for s in data['sources'] + data['vhdl_sources'])]}
    start = time.monotonic()
    jobs = []

    def step(args, *, artifact=None):
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            raise RuntimeError('wall-clock timeout')
        result = run_group(args, cwd=out, timeout=remaining, capture=True)
        index = len(jobs)
        (out / f'{index}.stdout').write_text(result.stdout or '')
        (out / f'{index}.stderr').write_text(result.stderr or '')
        jobs.append({'argv': args, 'returncode': result.returncode, 'timed_out': result.timed_out,
                     'stdout': f'{index}.stdout', 'stderr': f'{index}.stderr'})
        if result.timed_out or result.returncode:
            raise RuntimeError('wall-clock timeout' if result.timed_out else f'tool exited {result.returncode}')
        if artifact:
            (out / artifact).write_text(result.stdout or '')
        return result.stdout or ''

    status, reason = 'error', None
    try:
        versions = {}
        for tool, executable in paths.items():
            flag = '-V' if tool in ('yosys', 'iverilog', 'vvp') else '--version'
            # Icarus -V can print parts of its version on stderr.
            versions[tool] = step([executable, flag])
        sources = data['sources'][:]
        if data['backend'] == 'ghdl-yosys-icarus':
            step([paths['ghdl'], '--synth', '--std=08', '--out=verilog',
                  *data['vhdl_sources'], '-e', data['vhdl_top']], artifact='ghdl.v')
            # Fixed local names keep source paths outside the Yosys command language.
            script = 'read_verilog ghdl.v; hierarchy -check -top ' + data['vhdl_top']
            script += '; proc; opt; write_verilog -noattr mixed.v'
            step([paths['yosys'], '-Q', '-T', '-p', script])
            sources.append(str(out / 'mixed.v'))
        if data['backend'] == 'verilator-timing':
            step([paths['verilator'], '--binary', '--timing', '--assert', '-j', '1',
                  '--top-module', data['top'], '--Mdir', str(out / 'obj'),
                  '-o', 'sim', *sources])
            output = step([str(out / 'obj' / 'sim')])
        else:
            step([paths['iverilog'], '-g2012', '-s', data['top'], '-o', str(out / 'sim.vvp'), *sources])
            output = step([paths['vvp'], str(out / 'sim.vvp')])
        # An exit code alone is not evidence that the test reached its checks.
        if output.splitlines().count('RVW_PASS') != 1:
            reason = 'missing or duplicate RVW_PASS completion marker'
        else:
            status = 'pass'
    except (OSError, RuntimeError) as exc:
        reason = str(exc)
    report = {'schema': 'rvw.hdl-result/1', 'status': status, 'reason': reason,
              'backend': data['backend'], 'capabilities': PROFILES[data['backend']].to_dict(),
              'inputs': inputs, 'tools': paths, 'versions': versions, 'jobs': jobs,
              'wall_s': time.monotonic() - start, 'timeout_s': timeout,
              'replay': ['rvw', 'regress', 'hdl', str(manifest.resolve()), '--backend', data['backend'],
                         '--timeout', str(timeout), '--out', '<new-directory>']}
    write_json(out / 'results.json', report)
    return report
