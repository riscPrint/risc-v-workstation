"""Build and smoke-test project-owned privilege campaigns."""
from pathlib import Path
import hashlib
import json
import re
import shutil
from rvw.common.proc import run_group
from .programs import controls, LINK, SPEC


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    raw = json.loads(Path(path).read_text())
    if raw.get('schema') != 'rvw.privilege/1':
        raise ValueError('expected rvw.privilege/1')
    if set(raw) - {'pmp', 'stateen', 'landing', 'epmp', 'disabled', 'reri', 'dvfs', 'schema', 'modes', 'isa', 'priv', 'kind', 'timer', 'wake', 'plic', 'reset', 'nmi', 'compiler_isa', 'pma', 'imsic', 'aplic', 'spec_version', 'reference_backend', 'aclint', 'fast_interrupts', 'spec_revision', 'envcfg', 'sstc'}:
        raise ValueError('unknown campaign field')
    if raw.get('reference_backend','spike') not in ('spike','python'):
        raise ValueError('reference_backend must be spike or python')
    modes = raw.get('modes', ['M', 'S', 'U'])
    if not modes or len(set(modes)) != len(modes) or any(m not in (('M', 'S', 'U', 'mprv-s', 'mprv-u') if raw.get('kind') == 'pmp' else ('M', 'S', 'U')) for m in modes):
        raise ValueError('modes must be distinct M, S or U entries')
    if raw.get('priv', 'msu') != 'msu' and not (raw.get('kind') in ('disabled','disabled-matrix') and raw.get('priv') == 'mu'):
        raise ValueError('control campaign requires supervisor support (msu)')
    if raw.get('kind', 'controls') not in ('pma-access', 'reset-inflight', 'stateen-hierarchy', 'envcfg-zero', 'landing-recovery', 'sstc-rv32', 'aplic-msi', 'epmp-matrix', 'disabled-matrix', 'reri', 'dvfs', 'controls', 'wfi', 'disabled', 'scheduled-wfi', 'plic', 'reset', 'nmi', 'pma', 'pmp', 'epmp', 'imsic', 'aplic', 'aclint', 'smnip', 'sstc', 'stateen', 'envcfg', 'landing', 'shadow'):
        raise ValueError('kind must be controls, wfi or disabled')
    if raw.get('kind') == 'wfi':
        from .wake import programs
        programs(raw)
    return raw



def scenarios(config):
    from importlib import import_module
    kind = config.get('kind', 'controls')
    module = {'pma-access':'pma_access', 'reset-inflight':'reset_phase', 'stateen-hierarchy':'state_hierarchy', 'envcfg-zero':'env_behavior', 'landing-recovery':'cfi_recovery', 'sstc-rv32':'timer32', 'aplic-msi':'aplic_gateway', 'epmp-matrix':'epmp_matrix', 'disabled-matrix':'disabled_matrix', 'controls':'programs', 'wfi':'wake', 'scheduled-wfi':'scheduled',
              'reset':'lifecycle', 'nmi':'lifecycle', 'imsic':'aia', 'aplic':'aia',
              'aclint':'fast_interrupts', 'smnip':'fast_interrupts',
              'sstc':'extensions', 'stateen':'extensions', 'envcfg':'extensions', 'landing':'extensions'}.get(kind, kind)
    generator = import_module('rvw.privilege.' + module)
    return getattr(generator, 'controls' if kind == 'controls' else 'programs')(config)

def build(description, out, gcc='riscv64-unknown-elf-gcc'):
    config = load(description)
    rows = scenarios(config)
    if not rows:
        raise ValueError('campaign has no scenarios')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('output directory must be empty')
    (out / 'link.ld').write_text(LINK)
    for row in rows:
        name = row['id']
        source, elf = out / (name + '.S'), out / (name + '.elf')
        source.write_text(row.pop('assembly'))
        command = [gcc, '-march=' + config.get('compiler_isa', config.get('isa', 'rv64im_zicsr_zifencei')), '-mabi=' + ('ilp32' if config.get('isa','rv64').startswith('rv32') else 'lp64'),
                   '-nostdlib', '-nostartfiles', '-static', '-Wl,--no-relax', '-T', str(out / 'link.ld'),
                   *row.get('link_options', []), '-o', str(elf), str(source)]
        result = run_group(command, capture=True, timeout=30)
        if result.returncode:
            raise ValueError(f'{name}: compiler failed: {result.stderr}')
        if row.get('events'):
            events = [dict(id=f'event-{i}', kind='device', hart=0,
                           after=[f'event-{i-1}'] if i else [], group=f'event-{i}', required=True,
                           payload={**event, 'request_symbol': 'stimulus_step', 'ack_symbol': 'stimulus_ack'})
                      for i, event in enumerate(row['events'])]
            stimulus = out / (name + '.stimulus.json')
            stimulus.write_text(json.dumps(dict(schema='rvw.stimulus/1', events=events), indent=2) + '\n')
            row['stimulus_sha256'] = digest(stimulus)
            row.setdefault('options', {})['stimulus_file'] = str(stimulus)
        row.update(elf=elf.name, elf_sha256=digest(elf), source_sha256=digest(source))
    manifest = dict(schema='rvw.privilege-build/1', spec=SPEC, config=config,
                    description_sha256=digest(description), scenarios=rows)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'functional-groups.json').write_text(json.dumps({'replace_defaults': True, 'groups': [
        {'name': 'privilege_csr_mode', 'fields': ['csr', 'mode'], 'when': {'class': 'csr'},
         'domains': [['0x180', '0x300', '0x341', '0x342', '0x346', '0x347', '0x350', '0x351', '0x355', '0x35c', '0x150', '0x151', '0x15c', '0x250', '0x251', '0x25c', '0x600', '0x011', '0x14d', '0x15d', '0x24d', '0x25d', '0x30a', '0x31a', '0x60a', '0x61a', '0x605', '0x615', '0x606', '0x306', '0x344', '0x644'], ['M', 'S', 'U']]},
        {'name': 'privilege_trap', 'fields': ['cause', 'mode'],
         'when': {'event': 'trap', 'interrupt': False}, 'domains': [[1, 2, 5, 7, 8, 9, 10, 11, 15, 18, 22], ['M']]},
        {'name': 'privilege_irq', 'fields': ['cause', 'mode'],
         'when': {'event': 'trap', 'interrupt': True}, 'domains': [[3, 7, 11], ['M']]},
    ]}, indent=2) + '\n')
    # This fragment is merged into the project's regression config by the owner.
    suites = []
    for row in rows:
        suites.append('[suites.' + row['id'] + ']\nkind = "elf-dir"\ndir = "."\n'
            + 'glob = ' + json.dumps(row['elf']) + '\nstrip_suffix = ".elf"\n'
            + 'max_cycles = 30000\ntimeout_s = 30\n')
        if row.get('options'):
            suites.append('[suites.' + row['id'] + '.options]\n')
            suites.extend(key + ' = ' + json.dumps(value) + '\n' for key, value in row['options'].items())
    (out / 'suite.toml').write_text('\n'.join(suites))
    return manifest


def reference(directory, spike='spike', timeout=2):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['schema'] != 'rvw.privilege-build/1':
        raise ValueError('expected privilege build manifest')
    if manifest['config'].get('reference_backend') == 'python':
        from . import aia, fast_interrupts, controllers
        rows = []
        for scenario in manifest['scenarios']:
            if digest(directory / scenario['elf']) != scenario['elf_sha256']:
                raise ValueError('ELF changed since build')
            if 'reference_model' not in scenario:
                raise ValueError('no Python reference model for this scenario')
            from importlib import import_module
            model_kind = scenario['reference_model']['kind']
            model = import_module('rvw.privilege.aplic_gateway') if model_kind == 'aplic-msi' else import_module('rvw.privilege.' + model_kind) if model_kind in ('reri','dvfs') else fast_interrupts if model_kind in ('aclint','smnip') else aia
            rows.append(model.reference(scenario))
        models = [aia, fast_interrupts, controllers]
        if manifest['config'].get('kind') == 'aplic-msi':
            models.append(import_module('rvw.privilege.aplic_gateway'))
        if manifest['config'].get('kind') in ('reri','dvfs'):
            models.append(import_module('rvw.privilege.' + manifest['config']['kind']))
        return dict(schema='rvw.privilege-reference/1', scope='model-based Python reference; no DUT coverage',
                    evidence='model-based', manifest_sha256=digest(directory / 'manifest.json'),
                    model_sha256={Path(m.__file__).name:digest(m.__file__) for m in models},
                    status=verdict(rows), scenarios=rows)
    executable = shutil.which(spike)
    if not executable:
        raise ValueError('Spike executable not found')
    executable_hash = digest(executable)
    rows = []
    for scenario in manifest['scenarios']:
        elf = directory / scenario['elf']
        if digest(elf) != scenario['elf_sha256']:
            raise ValueError('ELF changed since build')
        if scenario.get('reference_unavailable'):
            rows.append(dict(id=scenario['id'], status='inconclusive',
                             reason=scenario['reference_unavailable']))
            continue
        command = ['nice', '-n', '10', executable, '--isa=' + manifest['config'].get('isa', 'rv64im_zicsr_zifencei'),
                   '--priv=' + manifest['config'].get('priv', 'msu'), '-m128', *scenario.get('reference_options',[]), str(elf)]
        result = run_group(command, capture=True, timeout=timeout)
        status = 'inconclusive'
        if not result.timed_out:
            if result.returncode == 0:
                status = 'pass'
            elif re.search(r'\*\*\* FAILED \*\*\*', result.stderr or ''):
                status = 'fail'
        rows.append(dict(id=scenario['id'], status=status, command=command, returncode=result.returncode,
                         stderr=result.stderr, elf_sha256=scenario['elf_sha256']))
    if digest(executable) != executable_hash:
        raise ValueError('Spike executable changed')
    return dict(schema='rvw.privilege-reference/1', scope='Spike self-check only; no DUT coverage',
                manifest_sha256=digest(directory / 'manifest.json'), executable_sha256=executable_hash,
                status=verdict(rows), scenarios=rows)


def verdict(rows):
    return 'fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if rows and all(r['status'] == 'pass' for r in rows) else 'inconclusive'


def check(directory, results, platform, timeout=10):
    """Require unique C1 success and complete strict Spike agreement for each bin."""
    import sys
    from rvw.results import load_run
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['schema'] != 'rvw.privilege-build/1':
        raise ValueError('expected privilege build manifest')
    runs = [load_run(p) for p in Path(results).rglob('result.json')]
    rows = []
    for scenario in manifest['scenarios']:
        elf = directory / scenario['elf']
        if digest(elf) != scenario['elf_sha256']:
            raise ValueError('ELF changed since build')
        same_elf = [r for r in runs if r.elf_sha256 == scenario['elf_sha256']]
        candidates = [r for r in same_elf if
            all(getattr(r,'extra',{}).get(k)==v for k,v in scenario.get('options',{}).items() if k!='stimulus_file')
            and (not scenario.get('stimulus_sha256') or getattr(r,'extra',{}).get('stimulus_sha256')==scenario['stimulus_sha256'])]
        row = dict(id=scenario['id'], status='inconclusive', bins=scenario['bins'],
                   reason='need one conclusive C1 result', comparison=None)
        if len(candidates) == 1:
            run = candidates[0]
            row['c1_sha256'] = digest(run.path / 'result.json')
            if not run.why_inconclusive and run.status != 'pass':
                row.update(status='fail', reason='C1 self-check failed')
                rows.append(row)
                continue
            if scenario.get('timer_contract'):
                from .timer_observe import check as timer_check
                artifact = run.artifacts.get('privilege_timer')
                observed = timer_check(scenario['timer_contract'],
                                       json.loads((run.path / artifact).read_text()) if artifact else [])
                row['timer'] = observed
                if artifact:
                    row['timer_sha256'] = digest(run.path / artifact)
                if observed['status'] != 'pass':
                    row.update(status=observed['status'],reason=observed.get('reason','incomplete timer observations'))
                    rows.append(row)
                    continue
            if scenario.get('dvfs_contract'):
                from .dvfs import observe
                artifact = run.artifacts.get('privilege_dvfs')
                observed = observe(scenario['dvfs_contract'],
                                   json.loads((run.path / artifact).read_text()) if artifact else [])
                row['dvfs'] = observed
                if artifact:
                    row['dvfs_sha256'] = digest(run.path / artifact)
                if observed['status'] != 'pass':
                    row.update(status=observed['status'],reason=observed['reason'])
                    rows.append(row)
                    continue
            if scenario.get('pma_expectation'):
                from .pma import observe
                artifact = run.artifacts.get('privilege_bus')
                observed = observe(scenario['pma_expectation'],
                                   json.loads((run.path / artifact).read_text()) if artifact else None)
                row['pma'] = observed
                if artifact:
                    row['pma_sha256'] = digest(run.path / artifact)
                if observed['status'] != 'pass':
                    row.update(status=observed['status'], reason=observed['reason'])
                    rows.append(row)
                    continue
            if scenario.get('reset_phase_contract'):
                from .reset_phase import observe as phase_check
                artifact=run.artifacts.get('privilege_reset_phase')
                observed=phase_check(scenario['reset_phase_contract'],
                                     json.loads((run.path/artifact).read_text()) if artifact else [])
                row['reset_phase']=observed
                if artifact:row['reset_phase_sha256']=digest(run.path/artifact)
                if observed['status']!='pass':
                    row.update(status=observed['status'],reason=observed.get('reason'))
                    rows.append(row)
                    continue
            if scenario.get('reset_contract'):
                from .events import reset_check
                artifact = run.artifacts.get('privilege_reset')
                observed = reset_check(scenario['reset_contract'],
                                       json.loads((run.path / artifact).read_text()) if artifact else [])
                row['reset'] = observed
                if artifact:
                    row['reset_sha256'] = digest(run.path / artifact)
                if observed['status'] != 'pass':
                    row.update(status=observed['status'], reason='reset observations incomplete or differ')
                    rows.append(row)
                    continue
            if scenario.get('clock_state'):
                from .scheduled import clock_check
                artifact = run.artifacts.get('privilege_clock')
                observed = clock_check(json.loads((run.path / artifact).read_text()) if artifact else [],
                                       scenario['clock_state'])
                row['clock'] = observed
                if artifact:
                    row['clock_sha256'] = digest(run.path / artifact)
                if observed['status'] != 'pass':
                    row.update(status=observed['status'], reason=observed['reason'])
                    rows.append(row)
                    continue
            if not run.why_inconclusive and run.status != 'pass':
                row.update(status='fail', reason='C1 self-check failed')
            elif not run.why_inconclusive:
                trace = run.artifacts.get('rvfi_trace')
                if trace and (run.path / trace).is_file():
                    command = [sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', 'reference',
                               '--elf', str(elf), '--trace', str(run.path / trace), '--platform', str(platform),
                               '--model', 'spike', '--strict', '--timeout', str(timeout), '--json']
                    result = run_group(command, capture=True, timeout=timeout + 5)
                    try:
                        comparison = json.loads(result.stdout or '{}')
                    except ValueError:
                        comparison = {}
                    row.update(comparison=comparison, reason='no complete strict reference match')
                    if not result.timed_out and comparison.get('status') == 'mismatch':
                        row.update(status='fail', reason='architectural mismatch')
                    elif (not result.timed_out and result.returncode == 0 and comparison.get('status') == 'match'
                          and comparison.get('trace_complete') is True and comparison.get('end_status') == 'pass'
                          and comparison.get('instructions', 0) > 0 and comparison.get('synchronized') == 0):
                        row.update(status='pass', reason=None)
        rows.append(row)
    groups = {}
    for name in sorted({b for r in rows for b in r['bins']}):
        groups[name] = verdict([r for r in rows if name in r['bins']])
    return dict(schema='rvw.privilege-check/1', manifest_sha256=digest(directory / 'manifest.json'),
                status=verdict(rows), scenarios=rows, groups=groups,
                counts={status: list(groups.values()).count(status) for status in ('pass', 'fail', 'inconclusive')})
