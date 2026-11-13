"""Seeded upstream pygen programs through C1, Spike and functional coverage."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import sys
import tomllib
import time
import shutil

from rvw.common.proc import run_group
from rvw.cosim.cli import execute_json as cosim
from rvw.cov.functional import functional
from rvw.regress.run_evidence import owned_run_paths
from rvw.results import load_run
from .config import Suite, load_config, positive_int, finite_number
from .plan import source_for
from .runner import PlanItem, RunOptions, run_plan

ROOT = Path(__file__).resolve().parents[4]
REVISION = 'f557b89ed6881a20515481a2585e9d004cd9642b'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def complete(comparison, run):
    return (comparison.get('status') == 'match'
            and comparison.get('synchronized', 0) == 0
            and comparison.get('trace_complete') is True
            and comparison.get('end_status') == 'pass'
            and comparison.get('instructions', 0) > 0
            and comparison['instructions'] == run.instret)


def verify(elf, results, platform, coverage_plan=None, test_id=None):
    """Qualify one ELF. Failed or incomplete runs earn no coverage."""
    runs = [load_run(p) for p in owned_run_paths(results)
            if test_id is None or p.parent.name == test_id]
    matches = [r for r in runs if r.elf_sha256 == digest(elf)]
    if len(matches) != 1:
        return dict(status='adapter_error', message='need exactly one C1 result for ELF')
    run = matches[0]
    evidence = dict(c1_result=str(run.path/'result.json'), c1_sha256=digest(run.path/'result.json'), c1_status=run.status,
                    ran=getattr(run, 'cycles', None) is not None)
    if run.status == 'timeout':
        return dict(evidence, status='timeout')
    if run.why_inconclusive:
        return dict(evidence, status='adapter_error', message=run.why_inconclusive)
    if run.status != 'pass':
        return dict(evidence, status='core_failure')
    trace = run.artifact('rvfi_trace')
    if trace is None:
        return dict(evidence, status='trace_error', message='C1 result has no C2 trace')
    comparison = cosim('check', elf=str(elf), trace=str(trace), platform=str(platform), model='spike', strict=True, core=run.core)
    if comparison.get('status') == 'mismatch':
        return dict(evidence, status='mismatch', comparison=comparison)
    if not complete(comparison, run) or comparison.get('applied_masks'):
        return dict(evidence, status='cosim_error', comparison=comparison)
    report = functional([trace], config=coverage_plan, platform=platform)
    return dict(evidence, status='pass', comparison=comparison, coverage=report,
                trace_sha256=digest(trace))


def execute_json(out, settings=None, seeds=1, seed_base=1, project=None, core=None, config=None, resume=False, jobs=1):
    """Settings are project-owned TOML. Paths are relative to that file."""
    positive_int(seeds, 'seeds')
    positive_int(jobs, 'jobs')
    if jobs > 4:
        raise ValueError('jobs must be at most 4')
    if type(seed_base) is not int:
        raise ValueError('seed_base must be an integer')
    if settings is None:
        from rvw.common.project import load_project
        selected_project = load_project(project, core=core)
        settings = selected_project.get('stimulus', 'random_settings') if selected_project else None
        if settings is None:
            raise ValueError('give settings or set stimulus.random_settings in rvw.toml')
    settings, out = Path(settings).resolve(), Path(out).resolve()
    raw = settings.read_bytes()
    data = tomllib.loads(raw.decode())
    required = {'checkout', 'python', 'target', 'isa', 'abi', 'linker', 'runtime', 'platform', 'compiler'}
    missing = required - data.keys()
    if missing:
        raise ValueError('missing random settings: '+', '.join(sorted(missing)))
    if data['target'] not in ('rv32imc', 'rv64imc'):
        raise ValueError('target must be rv32imc or rv64imc')
    if not data['isa'].lower().startswith(data['target'][:4]):
        raise ValueError('ISA and generator target have different XLEN')
    instructions = positive_int(data.get('instructions', 50), 'instructions')
    if instructions > 1000:
        raise ValueError('instructions must be at most 1000')
    classes = data.get('test_classes', ['arithmetic'])
    if not isinstance(classes, list) or not classes or any(c not in ('arithmetic', 'branches', 'load-store') for c in classes):
        raise ValueError('test_classes must select arithmetic, branches or load-store')
    timeout = finite_number(data.get('timeout_s', 120), 'timeout_s', positive=True)
    def path(key):
        p = Path(data[key]).expanduser()
        return p if p.is_absolute() else settings.parent / p
    selected = load_config(core, project=project)
    config = config or selected.default_config
    if config not in selected.configs:
        raise ValueError('unknown core configuration: '+config)
    checkout = path('checkout').resolve()
    # Source installation must remain outside every workstation checkout.
    if checkout == ROOT or ROOT in checkout.parents:
        raise ValueError('riscv-dv checkout must be outside the repository')
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=resume)
    report = dict(schema='rvw.random-campaign/1', status='inconclusive',
                  generator_revision=REVISION, settings_sha256=hashlib.sha256(raw).hexdigest(),
                  settings_source=str(settings), core=selected.name, config=config, attempts=[])
    report.update(seed_base=seed_base, seeds=seeds)
    inputs = {key: digest(path(key)) for key in ('platform', 'linker', 'target_profile') if data.get(key)}
    inputs['runtime'] = {str(p.relative_to(path('runtime'))): digest(p)
                        for p in sorted(path('runtime').rglob('*')) if p.is_file()}
    source = source_for(selected, None)
    report['inputs'] = inputs
    report['source'] = source.to_dict() if source else None
    from .source import describe
    report['tools_source'] = describe(ROOT).to_dict()
    if resume:
        previous = json.loads((out/'campaign.json').read_text())
        for key in ('generator_revision', 'settings_sha256', 'core', 'config', 'seed_base', 'seeds', 'inputs', 'source', 'tools_source'):
            if previous.get(key) != report.get(key):
                raise ValueError('resume input changed: '+key)
        for attempt in previous['attempts']:
            if attempt['status'] == 'pending':
                continue
            if attempt.get('c1_result') and digest(attempt['c1_result']) != attempt.get('c1_sha256'):
                raise ValueError('resume C1 evidence changed')
            elf = out/('seed-'+str(attempt['seed']))/'elfs/program.elf'
            if attempt.get('elf_sha256') and digest(elf) != attempt['elf_sha256']:
                raise ValueError('resume ELF changed')
        report = previous
    (out/'settings.toml').write_bytes(raw)
    def save():
        temporary = out/'campaign.json.tmp'
        temporary.write_text(json.dumps(report, indent=2)+'\n')
        temporary.replace(out/'campaign.json')
    save()
    pending = []
    terminal = {a['seed']: a for a in report['attempts'] if a['status'] != 'pending'}
    # Rebuild only incomplete attempts. Completed attempts remain immutable.
    report['attempts'] = [a for a in report['attempts'] if a['seed'] in terminal]

    for seed in range(seed_base, seed_base+seeds):
        if seed in terminal:
            continue
        attempt = dict(seed=seed, status='pending', test_class=classes[(seed-seed_base) % len(classes)])
        report['attempts'].append(attempt)
        directory = out / ('seed-'+str(seed))
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir()
        stage = 'generator_error'
        try:
            command = [sys.executable, str(ROOT/'scripts/riscv-dv-pygen.py'),
                       '--checkout', str(checkout), '--python', str(path('python')),
                       '--target', data['target'], '--seed', str(seed), '--instructions', str(instructions),
                       '--timeout', str(timeout), '--out', str(directory/'generated'),
                       '--test-class', attempt['test_class']]
            if data.get('target_profile'):
                command += ['--target-profile', str(path('target_profile'))]
            attempt['generate_argv'] = command
            with (directory/'generate.log').open('w') as log:
                result = run_group(command, timeout=timeout+10, stdout=log, stderr=log)
            if result.timed_out or result.returncode:
                raise ValueError('generator failed; see generate.log')
            assembly = directory/'generated/program_0.S'
            metadata = json.loads((directory/'generated/generation.json').read_text())
            if (metadata.get('status') != 'generated' or metadata.get('seed') != seed
                    or metadata.get('generator_revision') != REVISION
                    or metadata.get('source_sha256') != digest(assembly)):
                raise ValueError('generator metadata does not match output')
            if data.get('target_profile') and metadata.get('target_profile_sha256') != digest(path('target_profile')):
                raise ValueError('generator used a different target profile')
            attempt['generation'] = metadata
            stage = 'compile_error'
            elf_dir = directory/'elfs'
            elf_dir.mkdir()
            elf = elf_dir/'program.elf'
            command = [data['compiler'], '-march='+data['isa'], '-mabi='+data['abi'],
                       '-mcmodel=medany', '-nostdlib', '-nostartfiles', '-static',
                       '-I', str(path('runtime')), '-I', str(checkout/'user_extension'),
                       '-T', str(path('linker')), str(assembly), '-o', str(elf)]
            attempt['compile_argv'] = command
            attempt['linker_sha256'] = digest(path('linker'))
            attempt['runtime_sha256'] = {str(p.relative_to(path('runtime'))): digest(p)
                for p in sorted(path('runtime').rglob('*')) if p.is_file()}
            if not attempt['runtime_sha256']:
                raise ValueError('runtime directory has no input files')
            attempt['platform_sha256'] = digest(path('platform'))
            with (directory/'compile.log').open('w') as log:
                result = run_group(command, timeout=timeout, stdout=log, stderr=log)
            if result.timed_out or result.returncode or not elf.is_file():
                raise ValueError('compiler failed; see compile.log')
            attempt['elf_sha256'] = digest(elf)
            pending.append((attempt, elf))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            attempt.update(status=stage, message=str(exc))
        save()
    if pending:
        batch = out/'batch-elfs'
        if batch.exists():
            shutil.rmtree(batch)
        batch.mkdir()
        for attempt, elf in pending:
            shutil.copyfile(elf, batch/f"seed-{attempt['seed']}.elf")
        suite = Suite('riscv-dv', dir=batch, glob='*.elf', strip_suffix='.elf', timeout_s=timeout,
                      max_cycles=data.get('max_cycles', 1000000),
                      mem_latency=data.get('mem_latency'), options=data.get('run_options', {}))
        run_out = out/('run-'+str(time.time_ns()))
        try:
            run_plan(selected, [PlanItem(suite, config)], run_out, source,
                     RunOptions(seeds=1, seed_base=seed_base, rvfi_trace=True,
                                use_cache=False, jobs=jobs, index=False, tier='random'))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Published C1 results can still qualify other jobs after a batch failure.
            report['batch_error'] = str(exc)
        for attempt, elf in pending:
            try:
                attempt.update(verify(elf, run_out, path('platform'),
                                      path('coverage_plan') if data.get('coverage_plan') else None,
                                      'seed-'+str(attempt['seed'])))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                attempt.update(status='adapter_error', message=str(exc))
            save()
    report['attempts'].sort(key=lambda a: a['seed'])
    report['wall_s'] = report.get('wall_s', 0) + time.monotonic()-started
    statuses = [a['status'] for a in report['attempts']]
    report['counts'] = dict(sorted(Counter(statuses).items()))
    report['status'] = ('fail' if any(s in ('core_failure', 'mismatch', 'timeout') for s in statuses)
                        else 'pass' if statuses and all(s == 'pass' for s in statuses) else 'inconclusive')
    def counts(attempts):
        return dict(generated=sum('generation' in a for a in attempts),
                    compiled=sum('elf_sha256' in a for a in attempts),
                    run=sum(a.get('ran', False) for a in attempts),
                    match=sum(a['status'] == 'pass' for a in attempts),
                    mismatch=sum(a['status'] == 'mismatch' for a in attempts),
                    timeout=sum(a['status'] == 'timeout' for a in attempts),
                    generator_or_compile_error=sum(a['status'] in ('generator_error', 'compile_error') for a in attempts))
    report['summary'] = counts(report['attempts'])
    report['classes'] = {c: counts([a for a in report['attempts'] if a['test_class'] == c]) for c in classes}
    report['programs_per_hour'] = report['summary']['run'] * 3600 / report['wall_s']
    save()
    return report


def register(sub):
    cmd = sub.add_parser('random', help='generate pinned riscv-dv streams and check C1/C2 with Spike')
    cmd.add_argument('--settings', type=Path)
    cmd.add_argument('--out', required=True, type=Path)
    cmd.add_argument('--resume', action='store_true')
    cmd.add_argument('--jobs', type=int, default=1)
    cmd.add_argument('--seeds', type=int, default=1)
    cmd.add_argument('--seed-base', type=int, default=1)
    cmd.add_argument('--core')
    cmd.add_argument('--config')
    cmd.add_argument('--json', action='store_true')
    cmd.set_defaults(func=run)


def run(args):
    try:
        result = execute_json(args.out, args.settings, args.seeds, args.seed_base,
                              getattr(args, 'project', None), args.core, args.config, args.resume, args.jobs)
        code = {'pass': 0, 'fail': 1, 'inconclusive': 3}[result['status']]
    except (ValueError, OSError) as exc:
        result, code = dict(status='error', message=str(exc)), 2
    print(json.dumps(result))
    return code
