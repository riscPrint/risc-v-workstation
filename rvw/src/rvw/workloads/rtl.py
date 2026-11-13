"""Serial checked C1 benchmark campaigns, with explicit project build data."""
import hashlib
import json
import platform
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from rvw.common.project import find_project
from rvw.regress.config import load_config
from rvw.runs.adapter import Command, execute_many
from . import core


def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def run(out, project=None, settings=None, source=None, config=None, resume=False,
        timeout=110, repeats=1):
    project = find_project(project)
    if project is None:
        raise ValueError('a project is required')
    cfg = load_config(project=project)
    settings = Path(settings) if settings else project.parent / 'rvw/bench.json'
    data = json.loads(settings.read_text())
    if data.get('schema') != 'rvw.rtl-bench-settings/1':
        raise ValueError('expected rvw.rtl-bench-settings/1')
    if not 0 < timeout < 120 or repeats < 1:
        raise ValueError('timeout must be below 120 seconds; repeats must be positive')
    config = config or cfg.default_config
    if config not in cfg.configs:
        raise ValueError('unknown project config')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=resume)
    manifest = core.load(core.recipe(data.get('recipe', 'riscv-tests')))
    if data.get('recipe', 'riscv-tests') != 'riscv-tests':
        raise ValueError('RTL build currently supports the riscv-tests recipe')
    selected = data['programs']
    if not selected or len(set(selected)) != len(selected):
        raise ValueError('programs must be nonempty and unique')
    manifest['workloads'] = [w for w in manifest['workloads'] if w['id'] in selected]
    if {w['id'] for w in manifest['workloads']} != set(selected):
        raise ValueError('unknown workload')
    for w in manifest['workloads']:
        w['build'] += ['MARCH={march}', 'ABI={abi}']
    target = data['target']
    if not all(k in target for k in ('march', 'abi', 'ram_base', 'ram_size')):
        raise ValueError('target needs march, abi, ram_base and ram_size')
    for w in manifest['workloads']:
        w['build'] += ['RAM_BASE={ram_base}', 'RAM_SIZE={ram_size}']
        if data.get('bounded', False):
            w['build'] += ['RTL_VARIANT=bounded', 'SORT_SIZE={sort_size}', 'DHRYSTONE_RUNS={dhrystone_runs}', 'RUNTIME={runtime}', 'SPMV_ROWS={spmv_rows}']
            if w['id'] == 'dhrystone':
                w['checker'] = 'printed-final-values'
    if data.get('bounded', False):
        target = {'spmv_rows': 8, 'sort_size': 128, 'dhrystone_runs': 10, 'runtime': 'machine', **target}
    identity = []
    for repo in (project.parent, cfg.source_repo):
        if repo and Path(repo).exists():
            identity.append([subprocess.check_output(['git', '-C', str(repo), *args]).decode()
                             for args in (['rev-parse', 'HEAD'], ['diff', 'HEAD', '--'])])
    key = hashlib.sha256(json.dumps([data, config, repeats, timeout,
                                   core.digest(project), source, identity,
                                   {k: os.environ.get(k) for k in cfg.input_env}], sort_keys=True).encode()).hexdigest()
    report_path = out / 'report.json'
    if report_path.exists():
        report = json.loads(report_path.read_text())
        if not resume or report['key'] != key:
            raise ValueError('resume inputs differ; use a fresh output directory')
    else:
        report = {'schema': 'rvw.rtl-bench/1', 'key': key, 'project': str(project),
                  'config': config, 'machine': platform.node(),
                  'date': datetime.now(timezone.utc).isoformat(), 'workloads': []}
    build_path = out / 'build/build.json'
    if not build_path.exists():
        save(out / 'manifest.json', manifest)
        core.build(out / 'manifest.json', source or data['source'], out / 'build',
                   data.get('cc', 'riscv64-unknown-elf-gcc'), ','.join(selected), target=target, keep_going=True)
    build = json.loads(build_path.read_text())
    pending = [w for w in build['workloads'] if 'build_error' not in w and not any(
        r['program'] == w['id'] for r in report['workloads'])]
    commands, outputs = [], []
    for w in pending:
        if core.digest(w['elf']) != w['elf_sha256']:
            raise ValueError('ELF changed since build')
        for index in range(repeats):
            commands.append(Command(exe=cfg.adapter).set(elf=w['elf'], config=config, seed=1,
                max_cycles=data.get('max_cycles', 2000000), mem_latency=0, wall_timeout=timeout,
                probes=data.get('probes', False)))
            outputs.append(out / f"{w['id']}-{index}")
    attempts = iter(execute_many(commands, outputs, jobs=1, timeout=timeout))
    for w in build['workloads']:
        if 'build_error' not in w and core.digest(w['elf']) != w['elf_sha256']:
            raise ValueError('ELF changed since build')
        previous = next((r for r in report['workloads'] if r['program'] == w['id']), None)
        if previous:
            continue
        if 'build_error' in w:
            report['workloads'].append({'program': w['id'], 'status': 'fail', 'instructions': None,
                'cycles': None, 'ipc': None, 'triage': w['build_error'], 'samples': []})
            report['status'] = 'fail'
            save(report_path, report)
            (out / 'report.md').write_text(render(report))
            continue
        row = {'program': w['id'], 'elf_sha256': w['elf_sha256'], 'samples': [],
               'status': 'inconclusive', 'instructions': None, 'cycles': None, 'ipc': None}
        for index in range(repeats):
            attempt = next(attempts)
            sample = {'status': 'inconclusive', 'error': attempt.error, 'wall_s': attempt.wall}
            if attempt.run is not None:
                r = attempt.run
                sample.update(status=r.get('status'), instructions=r.get('instret'), cycles=r.get('cycles'), metrics=r.get('metrics', {}))
                if w['id'] == 'dhrystone' and not w.get('checker') and sample['status'] == 'pass':
                    sample.update(status='no_checks', error='upstream Dhrystone prints expected values but does not check them')
                # A C1 pass is the upstream program's HTIF self-check.
                if r.inconclusive or attempt.timed_out:
                    sample['status'] = 'inconclusive'
                if data.get('probes'):
                    from rvw.perf.topdown import report as analyze
                    try:
                        sample['topdown'] = analyze(attempt.dir / 'probe-events.jsonl', c1=attempt.dir / 'result.json')
                    except (OSError, ValueError, KeyError) as exc:
                        sample['topdown_error'] = str(exc)
            row['samples'].append(sample)
            # C1 collection can capture artifacts for replay. Remove those copies too.
            for name, path in getattr(attempt.run, 'captured_artifacts', {}).items():
                if name in ('probe_events', 'rvfi_trace', 'wave', 'konata'):
                    Path(path).unlink(missing_ok=True)
            # Remove optional adapter traces.
            for pattern in ('*.vcd*', '*.fst', '*rvfi*.jsonl', '*probe-events*.jsonl', '*kanata*'):
                for path in attempt.dir.glob(pattern):
                    if path.is_file():
                        path.unlink()
        first = row['samples'][0]
        row.update({k: first.get(k) for k in ('instructions', 'cycles', 'topdown')})
        row['deterministic'] = None if repeats < 2 else all(
            s['status'] == 'pass' and s.get('cycles', 0) > 0 and s.get('instructions') is not None and
            (s.get('instructions'), s.get('cycles')) == (row['instructions'], row['cycles'])
            for s in row['samples'])
        ok = all(s['status'] == 'pass' and isinstance(s.get('cycles'), int) and s['cycles'] > 0
                 and isinstance(s.get('instructions'), int) and s['instructions'] > 0 for s in row['samples'])
        row['status'] = 'pass' if ok else 'fail'
        if ok and row['cycles'] and row['instructions'] is not None:
            row['ipc'] = row['instructions'] / row['cycles']
        else:
            row['triage'] = '; '.join(str(s.get('error') or s['status']) for s in row['samples'])
        report['workloads'].append(row)
        report['status'] = 'pass' if all(r['status'] == 'pass' for r in report['workloads']) else 'fail'
        save(report_path, report)
        (out / 'report.md').write_text(render(report))
    return report


def render(report):
    lines = ['| Program | Instructions | Cycles | IPC | Status |', '|---|---:|---:|---:|---|']
    for r in report['workloads']:
        lines.append(f"| {r['program']} | {r['instructions']} | {r['cycles']} | {r['ipc']} | {r['status']} |")
    return '\n'.join(lines) + '\n'
