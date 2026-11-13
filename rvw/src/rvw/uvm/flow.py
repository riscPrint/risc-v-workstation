"""Project-owned SystemVerilog benches on pinned Accellera UVM."""
from __future__ import annotations
import datetime as dt
import json
import math
from pathlib import Path
import re
import shutil
import time
import urllib.request
from rvw.common.proc import run_group
from rvw.results import write_json
from rvw.sim import uvm


def load(manifest):
    path = Path(manifest).resolve(strict=True)
    data = json.loads(path.read_text())
    allowed = {'schema', 'name', 'top', 'sources', 'include_dirs', 'defines',
               'build_args', 'plusargs', 'tests', 'register_map', 'bindings'}
    if data.get('schema') != 'rvw.uvm/1' or set(data) - allowed:
        raise ValueError('expected rvw.uvm/1 manifest with supported fields')
    for key in ('name', 'top'):
        if not isinstance(data.get(key), str) or not re.fullmatch(r'[A-Za-z_]\w*', data[key]):
            raise ValueError(f'invalid {key}')
    for key in ('sources', 'include_dirs', 'defines', 'build_args', 'plusargs', 'tests'):
        value = data.setdefault(key, [])
        if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
            raise ValueError(f'{key} must be a string list')
    if not data['sources'] or not data['tests'] or len(set(data['tests'])) != len(data['tests']):
        raise ValueError('sources and unique tests are required')
    if any(not re.fullmatch(r'[A-Za-z_]\w*', t) for t in data['tests']):
        raise ValueError('invalid UVM test name')
    if any(not a.startswith('+') or a.startswith(('+UVM_TESTNAME', '+verilator+seed')) for a in data['plusargs']):
        raise ValueError('plusargs cannot override test or seed')
    for key in ('sources', 'include_dirs'):
        data[key] = [str((path.parent / p).resolve(strict=True)) for p in data[key]]
    if data.get('register_map'):
        data['register_map'] = str((path.parent / data['register_map']).resolve(strict=True))
    if 'bindings' in data and not isinstance(data['bindings'], dict):
        raise ValueError('bindings must be a project-owned object')
    return data


def limit(timeout):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be positive and finite')


def build(manifest, out, *, archive=None, verilator='verilator', timeout=600, required_features=()):
    limit(timeout)
    from rvw.sim.uvm_features import require
    require(required_features)
    data = load(manifest)
    executable = shutil.which(verilator)
    if not executable:
        raise ValueError('Verilator is not installed')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = [Path(manifest).resolve(), *map(Path, data['sources'])]
    for directory in data['include_dirs']:
        inputs.extend(p for p in Path(directory).rglob('*') if p.is_file())
    if data.get('register_map'):
        inputs.append(Path(data['register_map']))
    hashes = {str(p): uvm.sha(p) for p in inputs}
    if archive is None:
        archive = out / 'uvm.tar.gz'
        with urllib.request.urlopen(uvm.URL, timeout=30) as src, Path(archive).open('wb') as dst:
            shutil.copyfileobj(src, dst)
    library = uvm.unpack(Path(archive), out / 'library')
    sources = list(data['sources'])
    if data.get('register_map'):
        from rvw.sim.ral import generate
        (out / 'ral.sv').write_text(generate(data['register_map']))
        sources.insert(0, str(out / 'ral.sv'))
    top = data['top']
    harness = out / 'main.cpp'
    harness.write_text(f'''#include "V{top}.h"
#include "verilated.h"
#include "verilated_cov.h"
int main(int argc, char** argv) {{
 VerilatedContext context; context.commandArgs(argc, argv);
 V{top} model{{&context}};
 while (!context.gotFinish()) {{
  model.eval();
  if (!model.eventsPending()) break;
  context.time(model.nextTimeSlot());
 }}
 model.final(); context.coveragep()->write("coverage.dat");
 return 0;
}}
''')
    command = [executable, '--cc', '--exe', '--build', str(harness), '--timing', '--assert', '--coverage',
               '-Wno-fatal', '-j', '2', '--top-module', data['top'],
               '+define+UVM_NO_DPI', f'+incdir+{library / "src"}',
               *['+incdir+' + p for p in data['include_dirs']],
               *['+define+' + p for p in data['defines']],
               str(library / 'src/uvm_pkg.sv'), *sources, *data['build_args'],
               '--Mdir', str(out / 'obj'), '-o', 'simulation']
    with (out / 'build.log').open('w') as log:
        result = run_group(command, timeout=timeout, stdout=log, stderr=log)
    good = not result.timed_out and result.returncode == 0 and (out / 'obj/simulation').is_file()
    if any(not Path(p).is_file() or uvm.sha(p) != digest for p, digest in hashes.items()):
        good = False
    report = {'schema': 'rvw.uvm-build/1', 'status': 'pass' if good else 'error',
              'manifest': data, 'command': command, 'input_sha256': hashes,
              'uvm_commit': uvm.COMMIT, 'uvm_archive_sha256': uvm.ARCHIVE_SHA256,
              'binary_sha256': uvm.sha(out / 'obj/simulation') if good else None}
    write_json(out / 'build.json', report)
    return report


def evidence(text, test, returncode, timed_out):
    """A zero simulator exit alone is insufficient: UVM fatal may call $finish."""
    done = re.findall(r'^RVW_UVM_DONE (\w+) checks=(\d+)$', text, re.M)
    errors = re.search(r'^\s*UVM_(?:ERROR|FATAL)\b(?!\s*:\s*0\s*$)', text, re.M)
    if timed_out:
        return 'timeout', 'wall-clock timeout'
    if returncode or errors:
        return 'fail', 'simulator or UVM report failure'
    if len(done) != 1 or done[0][0] != test or int(done[0][1]) < 1:
        return 'error', 'missing completion marker or checked transactions'
    return 'pass', None


def run(build_dir, out, *, test, seed=1, timeout=120):
    limit(timeout)
    if type(seed) is not int or not 1 <= seed < 2**31:
        raise ValueError('seed must be in 1..2147483647')
    build_dir, out = Path(build_dir).resolve(), Path(out).resolve()
    built = json.loads((build_dir / 'build.json').read_text())
    if built['status'] != 'pass' or test not in built['manifest']['tests']:
        raise ValueError('build failed or test not declared')
    if any(not Path(p).is_file() or uvm.sha(p) != digest for p, digest in built['input_sha256'].items()):
        raise ValueError('build inputs changed; rebuild the bench')
    binary = build_dir / 'obj/simulation'
    if uvm.sha(binary) != built['binary_sha256']:
        raise ValueError('simulation binary changed')
    out.mkdir(parents=True, exist_ok=False)
    command = [str(binary), '+UVM_TESTNAME=' + test, f'+verilator+seed+{seed}',
               *built['manifest']['plusargs']]
    start = time.monotonic()
    with (out / 'run.log').open('w') as log:
        result = run_group(command, cwd=out, timeout=timeout, stdout=log, stderr=log)
    status, message = evidence((out / 'run.log').read_text(), test, result.returncode, result.timed_out)
    report = {'schema': 'rvw.run/1', 'core': built['manifest']['name'], 'config': test,
              'seed': seed, 'status': status, 'message': message,
              'cycles': None, 'instret': None, 'wall_s': time.monotonic() - start,
              'source': {'input_sha256': built['input_sha256'], 'identity_complete': False},
              'details': {'mode': 'uvm-bench', 'uvm_commit': uvm.COMMIT},
              'artifacts': {'log': 'run.log'}, 'command': command,
              'wall_clock_timeout': result.timed_out}
    if status == 'error':
        report['inconclusive'] = message
    if (out / 'coverage.dat').is_file():
        report['artifacts']['coverage'] = 'coverage.dat'
    write_json(out / 'result.json', report)
    return report


def regress(build_dir, out, *, tests=None, seeds=(1,), timeout=120):
    built = json.loads((Path(build_dir) / 'build.json').read_text())
    tests = built['manifest']['tests'] if tests is None else list(tests)
    seeds = list(seeds)
    if not tests or len(set(tests)) != len(tests) or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError('regression needs unique tests and seeds')
    if any(t not in built['manifest']['tests'] for t in tests):
        raise ValueError('test not declared')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for test in tests:
        for seed in seeds:
            name = f'{test}-{seed}'
            result = run(build_dir, out / name, test=test, seed=seed, timeout=timeout)
            rows.append({'id': test, 'seed': seed, 'kind': 'uvm', 'status': result['status'],
                         'signature': None if result['status'] == 'pass' else ('timeout:wall-clock' if result['wall_clock_timeout'] else 'uvm:' + result['status']),
                         'wall_clock_timeout': result['wall_clock_timeout'],
                         **({'inconclusive': result['inconclusive']} if 'inconclusive' in result else {}),
                         'artifacts': {'run': name + '/result.json', 'log': name + '/run.log'}})
    report = {'schema': 'rvw.results/1', 'suite': built['manifest']['name'],
              'core': built['manifest']['name'], 'config': 'uvm-verilator', 'run_id': out.name,
              'created': dt.datetime.now(dt.timezone.utc).isoformat(),
              'source': {'input_sha256': built['input_sha256'], 'identity_complete': False}, 'tests': rows}
    write_json(out / 'results.json', report)
    return report


def coverage_merge(inputs, out, *, tool='verilator_coverage', timeout=120):
    limit(timeout)
    inputs = [Path(p).resolve(strict=True) for p in inputs]
    if not inputs:
        raise ValueError('coverage inputs are required')
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('coverage output exists')
    result = run_group([tool, '--write', str(out), *map(str, inputs)], capture=True, timeout=timeout)
    if result.returncode or result.timed_out or not out.is_file():
        raise ValueError('coverage merge failed: ' + result.stdout)
    return {'output': str(out), 'inputs': list(map(str, inputs)), 'sha256': uvm.sha(out)}
