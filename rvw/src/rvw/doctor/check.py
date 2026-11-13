"""Setup diagnostics. Native version policy stays in scripts/install.sh."""
import json
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile

import rvw
from rvw.common.proc import run_group
from rvw.common.project import load_project
from rvw.regress.config import load_config
from rvw.regress.discover import discover

from . import backends
from .inventory import load as tool_inventory, report as inventory_report
from .conformance import smoke_options, artifacts

NATIVE_FEATURES = ('sim', 'riscv-gcc', 'cosim', 'formal', 'gem5')
NATIVE_FEATURES = tuple(dict.fromkeys([*NATIVE_FEATURES, *[t['flag'] for t in tool_inventory()['tools'] if t['flag'] != 'ide']]))
FEATURES = tuple(dict.fromkeys([*NATIVE_FEATURES, *backends.GUI]))


def features(value):
    names = list(FEATURES) if value == 'all' else list(dict.fromkeys(value.split(',')))
    if any(name not in FEATURES for name in names):
        raise ValueError('features must be all or a comma-separated list of ' + ','.join(FEATURES))
    return names


def native_records(output, table=None):
    """Keep installer evidence verbatim; a version probe is not a tested flow."""
    records = []
    for line in output.splitlines():
        match = re.match(r'^(PRESENT|WARNING|MISSING|UNUSABLE|UNKNOWN VERSION|WRONG VERSION|TOO OLD) (.*)$', line)
        if match:
            state, detail = match.groups()
            label, _, version = detail.partition(': ')
            tested = (table or {}).get({'javac': 'JDK', 'Sail': 'Sail RISC-V model'}.get(label, label))
            records.append({'installed': None if state == 'WARNING' else state != 'MISSING',
                            'tested_version': tested,
                            'tested_table_match': (version.split()[0] == tested.removesuffix('-dev')) if tested and version else None,
                            'support': 'unsupported' if state in ('WRONG VERSION', 'TOO OLD') else 'usable' if state == 'PRESENT' else 'unknown',
                            'status': 'ready' if state == 'PRESENT' else 'warning' if state == 'WARNING' else 'error',
                            'tool': label, 'version': version or None, 'evidence': line,
                            'qualification': 'version_probe_only'})
    return records


def diagnose(project=None, features='sim,riscv-gcc', install=None, yes=False, dry_run=False, smoke_elf=None, smoke_flags='', smoke_platform=None):
    checks = []
    def add(name, status, detail, fix=''):
        checks.append(dict(name=name, status=status, detail=detail, fix=fix))
    try:
        selected = globals()['features'](features)
        installing = list(NATIVE_FEATURES) if install == 'all' else globals()['features'](install) if install is not None else []
        if any(x not in NATIVE_FEATURES for x in installing):
            raise ValueError('GUI installation is manual. --install supports native features only.')
        options = smoke_options(smoke_flags)
        if (options or smoke_platform) and smoke_elf is None:
            raise ValueError('--smoke-options and --smoke-platform need --smoke-elf')
        if smoke_platform and 'rvfi' not in options:
            raise ValueError('--smoke-platform needs rvfi in --smoke-options')
        if (yes or dry_run) and install is None:
            raise ValueError('--yes and --dry-run need --install FEATURES')
    except ValueError as exc:
        return {'schema': 'rvw.doctor/1', 'status': 'error', 'exit_code': 2, 'checks': [], 'error': str(exc)}
    home = Path(os.environ.get('RVW_HOME', Path(__file__).resolve().parents[4]))
    script = home / 'scripts/install.sh'
    result = {'schema': 'rvw.doctor/1', 'rvw_version': rvw.__version__,
              'python_version': sys.version.split()[0], 'features': selected, 'checks': checks,
              'tool_inventory': inventory_report(),
              'qualification': 'No complete native tool combination is qualified by these diagnostics.'}
    add('python', 'ready' if sys.version_info >= (3, 11) else 'error', sys.version.split()[0], 'Install Python 3.11 or later.')
    if install is not None:
        command = ['bash', str(script), *['--with-' + x for x in installing]]
        if yes:
            command.append('--yes')
        if dry_run:
            command.append('--dry-run')
        # Prompts use the terminal. JSON keeps stdout separate from installer output.
        done = run_group(command, timeout=7200, capture=dry_run, stdout=None if dry_run else sys.stderr)
        result['installation'] = {'command': command, 'exit_code': done.returncode,
                                  'dry_run': dry_run, 'output': done.stdout if dry_run else None}
        add('installation', 'planned' if dry_run and done.returncode == 0 else 'ready' if done.returncode == 0 else 'error',
            'Installer exit ' + str(done.returncode), 'Read the installer log and source env.sh.')
    try:
        done = run_group(['bash', str(script), '--check', *['--with-' + x for x in selected if x in NATIVE_FEATURES]], timeout=120, capture=True)
        table = {}
        table_path = home / 'docs/TOOL_VERSIONS.md'
        if table_path.is_file():
            for line in table_path.read_text().splitlines():
                cells = [cell.strip() for cell in line.split('|')]
                if len(cells) >= 6 and re.match(r'^[0-9]', cells[2]):
                    table[cells[1]] = cells[2]
        result['tested_version_table'] = table
        result['native'] = native_records((done.stdout or '') + (done.stderr or ''), table)
        result['native_output'] = (done.stdout or '') + (done.stderr or '')
        add('native', 'ready' if done.returncode == 0 else 'error', f'Installer check exit {done.returncode}',
            'Source env.sh. Use --install FEATURES for missing tools.')
    except OSError as exc:
        add('native', 'error', str(exc), 'Set RVW_HOME to the workstation checkout.')
    result['backends'] = []
    capabilities = dict(sim=['build', 'run'], **{'riscv-gcc': ['elf_build'],
                        'cosim': ['reference_comparison'], 'formal': ['formal_checks'],
                        'gem5': ['architecture_model']})
    native_status = next(c['status'] for c in checks if c['name'] == 'native')
    for feature in FEATURES:
        if feature not in selected:
            backend = dict(feature=feature, status='skipped', reason='Feature not requested.')
        elif feature in backends.GUI:
            backend = backends.probe(feature)
            add('backend.' + feature, backend['status'], backend, backend['reason'])
        else:
            backend = dict(feature=feature, status=native_status,
                           capabilities=capabilities.get(feature, []), qualification='version_probe_only',
                           reason='Aggregate requested native installer check. See native records.')
        result['backends'].append(backend)
    try:
        config_project = load_project(project)
        if config_project is None:
            raise ValueError('No rvw.toml selected.')
        cfg = load_config(project=config_project.path)
        add('project', 'ready', str(config_project.path), '')
    except (ValueError, OSError, TypeError) as exc:
        add('project', 'error', str(exc), 'Run rvw init or fix the selected rvw.toml.')
        cfg = None
    if cfg:
        info = {}
        try:
            done = run_group([*cfg.adapter, 'info', '--json'], cwd=cfg.path.parent, timeout=30, capture=True)
            info = json.loads(done.stdout or '{}')
            valid = (done.returncode == 0 and isinstance(info, dict) and info.get('schema') == 'rvw.adapter/1'
                     and info.get('core') == cfg.name and info.get('configs') == cfg.configs
                     and info.get('default_config') == cfg.default_config
                     and info.get('xlen') in (32, 64) and isinstance(info.get('isa'), dict)
                     and all(isinstance(info['isa'].get(c), str) and info['isa'][c] for c in cfg.configs))
            add('adapter.info', 'ready' if valid else 'error', info, 'Implement C1 info --json for the selected core and configs.')
        except (OSError, ValueError) as exc:
            add('adapter.info', 'error', str(exc), 'Make the adapter executable and implement info --json.')
        if not isinstance(info, dict):
            info = {}
        if smoke_elf is None:
            add('adapter.build_run', 'inconclusive', 'Not run. info does not prove C1 build/run conformance.',
                'Use --smoke-elf ELF to build and run a small program. Review RVFI separately.')
        else:
            from rvw.results.schema import validate_run, RunResult
            try:
                smoke_hash = hashlib.sha256(Path(smoke_elf).read_bytes()).hexdigest()
                with tempfile.TemporaryDirectory(prefix='rvw-doctor-smoke-') as directory:
                    build_flags = ['--' + x for x in options]
                    run_flags = ['--rvfi-trace' if x == 'rvfi' else '--' + x for x in options]
                    build = run_group([*cfg.adapter, 'build', '--config', cfg.default_config, *build_flags, '--json'],
                                      cwd=cfg.path.parent, timeout=cfg.build_timeout_s, capture=True)
                    if build.returncode != 0:
                        raise ValueError('C1 build failed: ' + (build.stderr or build.stdout or ''))
                    run = run_group([*cfg.adapter, 'run', '--config', cfg.default_config,
                                     '--elf', str(Path(smoke_elf).resolve()), '--out', directory,
                                     '--max-cycles', '10000', '--seed', '1', *run_flags, '--json'],
                                    cwd=cfg.path.parent, timeout=120, capture=True)
                    record = json.loads((Path(directory) / 'result.json').read_text())
                    errors = validate_run(record)
                    valid = (run.returncode == 0 and not errors and record.get('status') == 'pass'
                             and RunResult.from_dict(record).why_inconclusive is None
                             and record.get('core') == cfg.name
                             and record.get('config') == cfg.default_config
                             and record.get('elf_sha256') == smoke_hash
                             and record.get('seed') == 1 and record.get('max_cycles') == 10000)
                    add('adapter.build_run', 'ready' if valid else 'error',
                        {'exit_code': run.returncode, 'errors': errors, 'result': record},
                        'Fix C1 build/run and completion mapping. This checks one config and ELF only.')
                    if valid:
                        checks.extend(artifacts(record, directory, options, info, elf=smoke_elf,
                                                core=cfg.name, config=cfg.default_config, platform=smoke_platform))
            except (OSError, ValueError, TypeError) as exc:
                add('adapter.build_run', 'error', str(exc), 'Implement C1 build/run and use a valid small ELF.')
        for name, suite in cfg.suites.items():
            tests = []
            try:
                tests = discover(suite) if suite.kind == 'elf-dir' else []
                valid = bool(tests) and all(t.elf.open('rb').read(4) == b'\x7fELF' for t in tests)
            except (OSError, ValueError):
                valid = False
            add('suite.' + name, 'ready' if valid else 'error', f'{len(tests)} selected test files; ELF magic checked only.',
                'Build the test ELFs and check suite selection, ISA and link addresses.')
        if not cfg.suites:
            add('suites', 'error', 'No test suites.', 'Add a suite and build its ELFs.')
        add('gate.inputs', 'ready' if cfg.input_complete and cfg.identity and cfg.identity_capture else 'inconclusive',
            {'input_complete': cfg.input_complete, 'identity': cfg.identity, 'identity_capture': cfg.identity_capture},
            'Review all result-changing inputs and implement identity capture before enabling these claims.')
        for label, root in [('core', cfg.source_repo or config_project.root), ('workstation', home)]:
            done = run_group(['git', '-C', str(root), 'status', '--porcelain'], timeout=10, capture=True)
            head = run_group(['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'], timeout=10, capture=True)
            add('gate.' + label, 'ready' if done.returncode == head.returncode == 0 and not done.stdout else 'inconclusive',
                {'revision': (head.stdout or '').strip(), 'changes': done.stdout}, 'Commit reviewed changes in this repository.')
    result['adapter_conformance'] = {'scope': 'one config and ELF; selected options only',
                                     'full_c1': 'inconclusive',
                                     'checks': [c for c in checks if c['name'].startswith('adapter.')]}
    ready = all(c['status'] == 'ready' for c in checks)
    result.update(status='ready' if ready else 'not_ready', exit_code=0 if ready else 1)
    return result
