"""Native gem5 runs. Architecture reports describe model gaps, never gate verdicts."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import runpy
import shutil

from rvw.common.lock import held
from rvw.common.proc import run_group
from rvw.common.project import load_project
from rvw.regress.config import load_config, positive_int, finite_number
from rvw.results import RunResult, write_json

ROOT = Path(__file__).resolve().parents[4]
# C1 launch supervisors allow 15 seconds for nested child cleanup.
C1_GRACE_S = 20.0
BENCHMARKS = ('median', 'qsort', 'rsort', 'towers', 'vvadd', 'memcpy', 'multiply', 'dhrystone', 'spmv')


class ArchError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(data):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ArchError(f'duplicate JSON key {k}')
            out[k] = v
        return out
    def constant(s):
        raise ArchError(f'invalid JSON number {s}')
    value = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ArchError('JSON document must be an object')
    return value


def selection(bench=None):
    names = list(BENCHMARKS) if bench is None else bench.split(',')
    if not names or any(re.fullmatch(r'[A-Za-z0-9_-]+', x) is None for x in names):
        raise ArchError('bench must be a nonempty comma-separated list of names')
    if len(set(names)) != len(names):
        raise ArchError('duplicate benchmark names')
    return names


def settings(project=None):
    p = load_project(project)
    if p is None or not p.get('arch', 'description'):
        raise ArchError('select a project with [arch] description, sources and benchmarks')
    for key in ('sources', 'benchmarks'):
        if not p.get('arch', key):
            raise ArchError(f'missing arch.{key}')
    data = Path(p.get('arch', 'description')).read_bytes()
    desc = read_json(data)
    if not isinstance(desc, dict) or desc.get('schema') != 'rvw.arch-core/1':
        raise ArchError('description needs schema rvw.arch-core/1')
    if not isinstance(desc.get('config'), str) or not desc['config']:
        raise ArchError('description needs a C1 config name')
    if desc.get('isa') not in ('rv64gc', 'rv64gc_zba_zbb_zbs') or desc.get('kind') != 'o3':
        raise ArchError('only rv64gc o3 models are supported')
    runpy.run_path(str(ROOT / 'Arch/model.py'))['validate_description'](desc)
    positive_int(desc.get('memory_latency'), 'memory_latency')
    return p, data, desc


def executable(name):
    path = shutil.which(str(name))
    if not path:
        raise ArchError(f'executable not found: {name}')
    return str(Path(path).resolve())


def gem5_binary():
    chosen = os.environ.get('RVW_GEM5')
    if chosen:
        return executable(chosen)
    candidate = ROOT / '.tools/src/gem5-v25.1.0.1/build/RISCV/gem5.opt'
    return executable(candidate if candidate.exists() else 'gem5.opt')


def invoke(command, log, *, cwd=None, env=None, timeout=600, grace=None):
    finite_number(timeout, 'timeout', positive=True)
    with Path(log).open('w') as f:
        result = run_group(['nice', *map(str, command)], cwd=cwd, env=env, timeout=timeout,
                           stdout=f, stderr=f, grace=grace)
    if result.returncode:
        raise ArchError(f'command exited {result.returncode}; see {log}')


def tool_identity(path, option="--version"):
    result = run_group([path, option], capture=True, timeout=30)
    if result.returncode:
        raise ArchError(f'cannot read tool version: {path}')
    return {'path': path, 'sha256': digest(Path(path).read_bytes()),
            'version': (result.stdout or '') + (result.stderr or '')}


def validate_gem5(tool):
    if re.search(r'^gem5 version 25\.1\.0\.1$', tool['version'], re.M) is None:
        raise ArchError('gem5 v25.1.0.1 is required')
    if re.search(r'^\s*USE_RISCV_ISA = True\s*$', tool['version'], re.M) is None:
        raise ArchError('gem5 RISC-V support is required')


def build(project=None, bench=None):
    p, _, desc = settings(project)
    names = selection(bench)
    binary = gem5_binary()
    gem5 = tool_identity(binary, "--build-info")
    validate_gem5(gem5)
    cc = executable(os.environ.get('RVW_RISCV_CC', 'riscv64-unknown-elf-gcc'))
    compiler = tool_identity(cc)
    out = Path(p.get('arch', 'benchmarks'))
    out.mkdir(parents=True, exist_ok=True)
    # Make uses the supplied GCC without picolibc or a Linux cross compiler.
    with held('arch-build'):
        invoke(['make', '-C', ROOT / 'Arch/bench', 'bare',
                f'SRC={p.get("arch", "sources")}', f'BARE_CC={cc}',
                f'BUILD={out}', f'MARCH={desc["isa"]}', 'BENCHES=' + ' '.join(names)], out / 'build.log')
    files = []
    for name in names:
        path = out / f'{name}.riscv'
        files.append({'id': name, 'path': str(path), 'sha256': digest(path.read_bytes())})
    result = {'schema': 'rvw.arch-build/1', 'config': desc['config'], 'isa': desc['isa'],
              'sources': str(p.get('arch', 'sources')),
              'gem5': gem5, 'compiler': compiler, 'benchmarks': files}
    write_json(out / 'build.json', result)
    return result


def prepare(project, bench, out):
    p, raw, desc = settings(project)
    names = selection(bench)
    out = Path(out).absolute()
    # A fresh directory prevents old C1 files from turning failed runs into evidence.
    out.mkdir(parents=True, exist_ok=False)
    inputs = out / 'inputs'
    inputs.mkdir()
    (inputs / 'description.json').write_bytes(raw)
    (inputs / 'rvw.toml').write_bytes(p.path.read_bytes())
    model = (ROOT / 'Arch/model.py').read_bytes()
    (inputs / 'model.py').write_bytes(model)
    build_path = Path(p.get('arch', 'benchmarks')) / 'build.json'
    build_info = None
    if build_path.is_file():
        build_bytes = build_path.read_bytes()
        build_info = read_json(build_bytes)
        if build_info.get('schema') != 'rvw.arch-build/1':
            raise ArchError('invalid benchmark build manifest')
        (inputs / 'build.json').write_bytes(build_bytes)
    files = []
    for name in names:
        source = Path(p.get('arch', 'benchmarks')) / f'{name}.riscv'
        raw_elf = source.read_bytes()
        target = inputs / f'{name}.riscv'
        target.write_bytes(raw_elf)
        if build_info is not None:
            entries = build_info.get('benchmarks')
            if not isinstance(entries, list) or any(not isinstance(r, dict) for r in entries):
                raise ArchError('invalid benchmark build entries')
            matches = [r for r in entries if r.get('id') == name]
            if len(matches) != 1 or matches[0].get('sha256') != digest(raw_elf):
                raise ArchError(f'{name}: ELF does not match benchmark build manifest')
        files.append({'id': name, 'elf': str(target), 'elf_sha256': digest(raw_elf)})
    context = {'core': p.name, 'config': desc['config'], 'memory_latency': desc['memory_latency'],
               'description_sha256': digest(raw), 'model_sha256': digest(model),
               'project': str(p.path), 'project_capture': p.capture,
               'benchmark_build': build_info}
    write_json(out / 'inputs.json', {**context, 'benchmarks': files})
    return p, desc, out, files, context


def collect_bare(data):
    if (type(data.get('exit_code')) is not int or data['exit_code'] != 0
            or type(data.get('tohost')) is not int or data['tohost'] != 1):
        raise ArchError('gem5 did not report a passing tohost exit')
    stats = data.get('bench_stats', {})
    if not isinstance(stats, dict):
        raise ArchError('gem5 bench_stats must be an object')
    for key in ('cycles', 'instret'):
        positive_int(stats.get(key), f'gem5 ROI {key}')
    if data.get('roi') != 'setStats':
        raise ArchError('missing gem5 ROI markers')
    return {'cycles': stats['cycles'], 'instret': stats['instret']}


def run_models(out, files, context, timeout):
    binary = gem5_binary()
    tool = tool_identity(binary, "--build-info")
    validate_gem5(tool)
    rows = []
    with held('gem5'):
        # Serial by design. Every invocation holds the machine-wide gem5 lock.
        for item in files:
            directory = out / 'gem5' / item['id']
            directory.mkdir(parents=True)
            invoke([binary, f'--outdir={directory}', out / 'inputs/model.py',
                    '--description', out / 'inputs/description.json', item['elf']],
                   directory / 'run.log', timeout=timeout)
            evidence = (directory / 'bare.json').read_bytes()
            rows.append({**item, **collect_bare(read_json(evidence)), 'status': 'pass',
                         'evidence': str(directory / 'bare.json'), 'evidence_sha256': digest(evidence)})
    result = {'schema': 'rvw.arch-run/1', 'engine': 'gem5', **context, 'tool': tool, 'benchmarks': rows}
    write_json(out / 'gem5.json', result)
    return result


def run(project=None, bench=None, out='arch-run', timeout=600):
    _, _, out, files, context = prepare(project, bench, out)
    return run_models(out, files, context, timeout)


def collect_rtl(raw, item, context):
    run = RunResult.from_dict(raw)
    if run.status != 'pass' or run.why_inconclusive:
        raise ArchError(f'RTL run is not a conclusive pass: {run.status}, {run.why_inconclusive}')
    if (run.elf_sha256 != item['elf_sha256'] or run.config != context['config']
            or run.core != context['core'] or run.mem_latency != context['memory_latency']
            or run.seed != 1):
        raise ArchError('RTL result does not match ELF, core, config, seed or memory latency')
    metrics = raw.get('metrics', {})
    if not isinstance(metrics, dict):
        raise ArchError('RTL ROI metrics must be an object')
    cycles, instret = metrics.get('roi_cycles'), metrics.get('roi_instret')
    positive_int(cycles, 'RTL ROI cycles')
    positive_int(instret, 'RTL ROI instret')
    return {'cycles': cycles, 'instret': instret}


def calibrate(project=None, bench=None, out='arch-calibration', timeout=3600):
    p, desc, out, files, context = prepare(project, bench, out)
    config = load_config(project=p.path)
    if desc['config'] not in (config.configs or [config.default_config]):
        raise ArchError(f'unknown C1 config {desc["config"]}')
    rtl = out / 'rtl'
    rtl.mkdir()
    manifest = rtl / 'jobs.jsonl'
    jobs = [{'elf': item['elf'], 'out': str(rtl / item['id']), 'config': desc['config'],
             'seed': 1, 'mem_latency': desc['memory_latency'], 'max_cycles': 50000000}
            for item in files]
    manifest.write_text(''.join(json.dumps(job) + '\n' for job in jobs))
    env = dict(os.environ)
    if config.source_env:
        env[config.source_env] = str(config.source_repo)
    # Use the project's C1 adapter. Its lock name selects the core's shared resource.
    with held(config.lock, directory=config.lock_dir):
        invoke([ROOT / 'scripts/with-lock.sh', config.lock or 'arch-rtl',
                *config.adapter, 'run-many', '--manifest', manifest, '--jobs', '1'],
               rtl / 'run.log', cwd=p.root, env=env, timeout=timeout, grace=C1_GRACE_S)
    rows = []
    for item in files:
        path = rtl / item['id'] / 'result.json'
        evidence = path.read_bytes()
        rows.append({**item, **collect_rtl(read_json(evidence), item, context), 'status': 'pass',
                     'evidence': str(path), 'evidence_sha256': digest(evidence)})
    result = {'schema': 'rvw.arch-run/1', 'engine': 'rtl', **context, 'benchmarks': rows}
    write_json(out / 'rtl.json', result)
    run_models(out, files, context, timeout)
    report = compare(out / 'rtl.json', out / 'gem5.json')
    write_json(out / 'calibration.json', report)
    (out / 'summary.txt').write_text(summary(report) + '\n')
    return report


def checked_report(path):
    raw = Path(path).read_bytes()
    data = read_json(raw)
    if data.get('schema') != 'rvw.arch-run/1' or data.get('engine') not in ('rtl', 'gem5'):
        raise ArchError('compare requires rvw.arch-run/1 reports')
    for key in ('core', 'config'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ArchError(f'report needs a nonempty {key}')
    positive_int(data.get('memory_latency'), 'report memory_latency')
    rows = data.get('benchmarks')
    if not isinstance(rows, list) or not rows:
        raise ArchError('empty benchmark report')
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
            raise ArchError('benchmark rows need nonempty IDs')
        name = row['id']
        if name in indexed:
            raise ArchError(f'duplicate benchmark {name}')
        if row.get('status') != 'pass':
            raise ArchError(f'{name}: run did not pass')
        elf = Path(row['elf']).read_bytes()
        evidence = Path(row['evidence']).read_bytes()
        if digest(elf) != row['elf_sha256'] or digest(evidence) != row['evidence_sha256']:
            raise ArchError(f'{name}: changed ELF or run evidence')
        values = (collect_bare(read_json(evidence)) if data['engine'] == 'gem5'
                  else collect_rtl(read_json(evidence), row, data))
        if any(row.get(k) != values[k] for k in ('cycles', 'instret')):
            raise ArchError(f'{name}: counters differ from run evidence')
        indexed[name] = row
    return data, indexed, digest(raw)


def compare(base, candidate, project=None):
    if project is not None:
        load_project(project)
    a, aa, ah = checked_report(base)
    b, bb, bh = checked_report(candidate)
    if set(aa) != set(bb):
        raise ArchError('benchmark sets differ')
    for key in ('core', 'config', 'memory_latency'):
        if a[key] != b[key]:
            raise ArchError(f'comparison {key} differs')
    rows, ratios = [], []
    for name in sorted(aa):
        x, y = aa[name], bb[name]
        if x['elf_sha256'] != y['elf_sha256'] or x['instret'] != y['instret']:
            raise ArchError(f'{name}: ELF or ROI instruction count differs')
        ratio = x['cycles'] / y['cycles']
        ratios.append(ratio)
        rows.append({'id': name, 'elf_sha256': x['elf_sha256'], 'instret': x['instret'],
                     'base_cycles': x['cycles'], 'candidate_cycles': y['cycles'],
                     'base_ipc': x['instret'] / x['cycles'], 'candidate_ipc': y['instret'] / y['cycles'],
                     'ipc_ratio': ratio, 'cycle_gap_percent': (y['cycles'] / x['cycles'] - 1) * 100})
    return {'schema': 'rvw.arch-compare/1', 'base': str(Path(base).absolute()),
            'candidate': str(Path(candidate).absolute()), 'base_sha256': ah, 'candidate_sha256': bh,
            'core': a['core'], 'config': a['config'], 'memory_latency': a['memory_latency'],
            'status': 'reported', 'benchmarks': rows,
            'geomean_ipc_ratio': math.exp(sum(math.log(r) for r in ratios) / len(ratios)),
            'limits': 'No fit or acceptance threshold. gem5 shows trends; RTL is the truth.'}


def summary(report):
    lines = ['benchmark        RTL cycles  model cycles  IPC ratio']
    for r in report['benchmarks']:
        lines.append(f'{r["id"]:16s} {r["base_cycles"]:10d} {r["candidate_cycles"]:13d} {r["ipc_ratio"]:10.3f}')
    lines.append(f'Geomean IPC ratio: {report["geomean_ipc_ratio"]:.3f}')
    lines.append(report['limits'])
    return '\n'.join(lines)
