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
    if set(raw) - {'schema', 'modes', 'isa', 'priv', 'kind', 'timer', 'wake'}:
        raise ValueError('unknown campaign field')
    modes = raw.get('modes', ['M', 'S', 'U'])
    if not modes or len(set(modes)) != len(modes) or any(m not in ('M', 'S', 'U') for m in modes):
        raise ValueError('modes must be distinct M, S or U entries')
    if raw.get('priv', 'msu') != 'msu' and not (raw.get('kind') == 'disabled' and raw.get('priv') == 'mu'):
        raise ValueError('control campaign requires supervisor support (msu)')
    if raw.get('kind', 'controls') not in ('controls', 'wfi', 'disabled', 'scheduled-wfi'):
        raise ValueError('kind must be controls, wfi or disabled')
    if raw.get('kind') == 'wfi':
        from .wake import programs
        programs(raw)
    return raw


def build(description, out, gcc='riscv64-unknown-elf-gcc'):
    config = load(description)
    if config.get('kind') == 'scheduled-wfi':
        from .scheduled import programs
        rows = programs(config)
    elif config.get('kind') == 'disabled':
        from .disabled import programs
        rows = programs(config)
    elif config.get('kind') == 'wfi':
        from .wake import programs
        rows = programs(config)
    else:
        rows = controls(config)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('output directory must be empty')
    (out / 'link.ld').write_text(LINK)
    for row in rows:
        name = row['id']
        source, elf = out / (name + '.S'), out / (name + '.elf')
        source.write_text(row.pop('assembly'))
        command = [gcc, '-march=' + config.get('isa', 'rv64im_zicsr_zifencei'), '-mabi=lp64',
                   '-nostdlib', '-nostartfiles', '-static', '-Wl,--no-relax', '-T', str(out / 'link.ld'),
                   '-o', str(elf), str(source)]
        result = run_group(command, capture=True, timeout=30)
        if result.returncode:
            raise ValueError(f'{name}: compiler failed: {result.stderr}')
        row.update(elf=elf.name, elf_sha256=digest(elf), source_sha256=digest(source))
    manifest = dict(schema='rvw.privilege-build/1', spec=SPEC, config=config,
                    description_sha256=digest(description), scenarios=rows)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'functional-groups.json').write_text(json.dumps({'replace_defaults': True, 'groups': [
        {'name': 'privilege_csr_mode', 'fields': ['csr', 'mode'], 'when': {'class': 'csr'},
         'domains': [['0x180', '0x300', '0x341', '0x342'], ['M', 'S', 'U']]},
        {'name': 'privilege_trap', 'fields': ['cause', 'mode'],
         'when': {'event': 'trap', 'interrupt': False}, 'domains': [[2, 8, 9, 11], ['M']]},
        {'name': 'privilege_irq', 'fields': ['cause', 'mode'],
         'when': {'event': 'trap', 'interrupt': True}, 'domains': [[3, 7], ['M']]},
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
                   '--priv=' + manifest['config'].get('priv', 'msu'), '-m128', str(elf)]
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
        candidates = [r for r in runs if r.elf_sha256 == scenario['elf_sha256']]
        row = dict(id=scenario['id'], status='inconclusive', bins=scenario['bins'],
                   reason='need one conclusive C1 result', comparison=None)
        if len(candidates) == 1:
            run = candidates[0]
            row['c1_sha256'] = digest(run.path / 'result.json')
            if any(run.extra.get(k) != v for k, v in scenario.get('options', {}).items()):
                row['reason'] = 'C1 stimulus options differ'
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
