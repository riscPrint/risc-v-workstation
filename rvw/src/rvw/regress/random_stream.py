"""Seeded upstream pygen programs through C1, Spike and functional coverage."""
from pathlib import Path
import hashlib
import json
import sys
import tomllib

from rvw.common.proc import run_group
from rvw.cosim.cli import execute_json as cosim
from rvw.cov.functional import functional
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
            and comparison.get('trace_complete') is True
            and comparison.get('end_status') == 'pass'
            and comparison.get('instructions', 0) > 0
            and comparison['instructions'] == run.instret)


def verify(elf, results, platform, coverage_plan=None):
    """Qualify one ELF. Failed or incomplete runs earn no coverage."""
    runs = [load_run(p) for p in Path(results).rglob('result.json')]
    matches = [r for r in runs if r.elf_sha256 == digest(elf)]
    if len(matches) != 1:
        return dict(status='adapter_error', message='need exactly one C1 result for ELF')
    run = matches[0]
    if run.why_inconclusive:
        return dict(status='adapter_error', message=run.why_inconclusive)
    if run.status != 'pass':
        return dict(status='core_failure', c1_status=run.status)
    trace = run.artifact('rvfi_trace')
    if trace is None:
        return dict(status='trace_error', message='C1 result has no C2 trace')
    comparison = cosim('check', elf=str(elf), trace=str(trace), platform=str(platform), model='spike', core=run.core)
    if comparison.get('status') == 'mismatch':
        return dict(status='mismatch', comparison=comparison)
    if not complete(comparison, run):
        return dict(status='cosim_error', comparison=comparison)
    report = functional([trace], config=coverage_plan, platform=platform)
    return dict(status='pass', comparison=comparison, coverage=report,
                trace_sha256=digest(trace), c1_result=str(run.path / 'result.json'))


def execute_json(out, settings=None, seeds=1, seed_base=1, project=None, core=None, config=None):
    """Settings are project-owned TOML. Paths are relative to that file."""
    positive_int(seeds, 'seeds')
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
    out.mkdir(parents=True, exist_ok=False)
    (out/'settings.toml').write_bytes(raw)
    report = dict(schema='rvw.random-campaign/1', status='inconclusive',
                  generator_revision=REVISION, settings_sha256=hashlib.sha256(raw).hexdigest(),
                  settings_source=str(settings), core=selected.name, config=config, attempts=[])
    def save():
        (out/'campaign.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    source = source_for(selected, None)
    for seed in range(seed_base, seed_base+seeds):
        attempt = dict(seed=seed, status='generator_error')
        report['attempts'].append(attempt)
        directory = out / ('seed-'+str(seed))
        directory.mkdir()
        stage = 'generator_error'
        try:
            command = [sys.executable, str(ROOT/'scripts/riscv-dv-pygen.py'),
                       '--checkout', str(checkout), '--python', str(path('python')),
                       '--target', data['target'], '--seed', str(seed), '--instructions', str(instructions),
                       '--timeout', str(timeout), '--out', str(directory/'generated')]
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
            stage = 'adapter_error'
            suite = Suite('riscv-dv', dir=elf_dir, glob='*.elf', strip_suffix='.elf', timeout_s=timeout,
                          max_cycles=data.get('max_cycles', 1000000))
            run_plan(selected, [PlanItem(suite, config)], directory/'run', source,
                                  RunOptions(seeds=1, seed_base=seed, rvfi_trace=True,
                                             use_cache=False, jobs=1, index=False, tier='random'))
            stage = 'cosim_error'
            attempt.update(verify(elf, directory/'run', path('platform'),
                                  path('coverage_plan') if data.get('coverage_plan') else None))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            attempt.update(status=stage, message=str(exc))
        save()
    statuses = [a['status'] for a in report['attempts']]
    report['status'] = ('fail' if any(s in ('core_failure', 'mismatch') for s in statuses)
                        else 'pass' if statuses and all(s == 'pass' for s in statuses) else 'inconclusive')
    save()
    return report


def register(sub):
    cmd = sub.add_parser('random', help='generate pinned riscv-dv streams and check C1/C2 with Spike')
    cmd.add_argument('--settings', type=Path)
    cmd.add_argument('--out', required=True, type=Path)
    cmd.add_argument('--seeds', type=int, default=1)
    cmd.add_argument('--seed-base', type=int, default=1)
    cmd.add_argument('--core')
    cmd.add_argument('--config')
    cmd.add_argument('--json', action='store_true')
    cmd.set_defaults(func=run)


def run(args):
    try:
        result = execute_json(args.out, args.settings, args.seeds, args.seed_base,
                              getattr(args, 'project', None), args.core, args.config)
        code = {'pass': 0, 'fail': 1, 'inconclusive': 3}[result['status']]
    except (ValueError, OSError) as exc:
        result, code = dict(status='error', message=str(exc)), 2
    print(json.dumps(result))
    return code
