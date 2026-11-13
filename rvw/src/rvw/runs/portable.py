"""Single-file, offline source/input replay. No native snapshot portability claim."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
import uuid
import zipfile

from rvw.common.proc import run_group
from rvw.runs import adapter
from rvw.runs.signature import signature
from rvw.results import RunResult


def digest(data):
    return hashlib.sha256(data).hexdigest()


def step(command, *, cwd=None, timeout=120, env=None):
    result = run_group(command, cwd=cwd, timeout=timeout, env=env, capture=True, text=True)
    if result.returncode or result.timed_out:
        raise ValueError('replay command failed: ' + result.stdout[-1500:] + result.stderr[-1500:])
    return result.stdout.strip()


def git_bundle(repo, revision, destination):
    ref = 'refs/rvw-replay/' + uuid.uuid4().hex
    step(['git', '-C', str(repo), 'update-ref', ref, revision])
    try:
        step(['git', '-C', str(repo), 'bundle', 'create', str(destination), ref])
    finally:
        step(['git', '-C', str(repo), 'update-ref', '-d', ref])
    return ref


def trace_events(path):
    from rvw.cosim.trace import Trace
    checked = Trace(Path(path))
    try:
        list(checked)
    finally:
        checked.close()
    rows = [json.loads(line) for line in Path(path).read_bytes().splitlines()]
    if not rows or rows[0].get('schema') not in ('rvw.rvfi/1', 'rvw.rvfi/2') or rows[-1].get('event') != 'end':
        raise ValueError('portable replay needs a complete C2 trace')
    return rows[1:]


def trace_header(path):
    header = json.loads(Path(path).open().readline())
    return {key: value for key, value in header.items() if key not in ('elf', 'source')}


def event_digest(events):
    return digest(json.dumps(events, sort_keys=True, separators=(',', ':')).encode())


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('unsafe replay archive path')
    return path


def pack(run_dir, recipe, out, *, checkpoint_cycle=None):
    run_dir = Path(run_dir).resolve()
    raw = json.loads((run_dir / 'result.json').read_bytes())
    validated = RunResult.from_dict(raw)
    if validated.why_inconclusive or raw.get('schema') != 'rvw.run/1' or raw.get('inconclusive') or raw.get('status') == 'pass':
        raise ValueError('portable replay needs a conclusive failing C1 run')
    data = json.loads(Path(recipe).read_bytes())
    if data.get('schema') != 'rvw.replay-adapter/1':
        raise ValueError('unsupported replay adapter recipe')
    if raw.get('wall_clock_timeout') or not isinstance(raw.get('rtl_sha256'), str) or len(raw['rtl_sha256']) != 64:
        raise ValueError('portable replay needs RTL identity and a deterministic terminal event')
    command = adapter.command_for(raw)
    job = adapter._manifest_entry(command)
    for name in ('out', 'json'):
        job.pop(name, None)
    for name in ('boot_payloads', 'hart_images', 'fault', 'debug', 'debug_binding', 'trace_ingress', 'stimulus_file'):
        if name in job:
            raise ValueError('portable replay does not capture structured input: ' + name)
    elf = Path(raw['elf']).resolve(strict=True)
    if digest(elf.read_bytes()) != raw['elf_sha256']:
        raise ValueError('recorded ELF digest differs')
    events = trace_events(run_dir / raw['artifacts']['rvfi_trace'])
    cycle = checkpoint_cycle if checkpoint_cycle is not None else max(1, raw['cycles'] // 2)
    if not 0 < cycle < raw['cycles']:
        raise ValueError('checkpoint cycle must be inside the failing run')
    checkpoint = dict(schema='rvw.portable-trace-checkpoint/1', mode='from-reset', cycle=cycle,
                      prefix_sha256=event_digest([e for e in events if e.get('cycle', -1) < cycle]),
                      suffix_sha256=event_digest([e for e in events if e.get('cycle', -1) >= cycle]))
    source = raw['source']
    revisions = {'tools': source['tools_rev'], 'core': source.get('core_rev_full', source.get('core_rev'))}
    repos = {'tools': Path(source['tools_repo']), 'core': Path(source['core_repo'])}
    with tempfile.TemporaryDirectory(prefix='rvw-pack-') as directory:
        stage = Path(directory)
        blobs = {}
        def add(name, payload, mode=0o644):
            safe_name(name)
            blobs[name] = (payload, mode)
        add('program.elf', elf.read_bytes())
        add('recipe.json', json.dumps(data, sort_keys=True).encode())
        add('checkpoint.json', json.dumps(checkpoint, sort_keys=True).encode())
        add('expected-header.json', json.dumps(trace_header(run_dir / raw['artifacts']['rvfi_trace']), sort_keys=True).encode())
        add('expected-events.json', json.dumps(events, sort_keys=True).encode())
        if 'soc_map' in job:
            map_path = run_dir / raw['artifacts']['soc_map']
            if digest(map_path.read_bytes()) != raw.get('soc_map_sha256'):
                raise ValueError('captured simulation map digest differs')
            add('stimulus/sim-map.json', map_path.read_bytes())
            job['soc_map'] = '{archive}/stimulus/sim-map.json'
        refs = {}
        for kind, repo in repos.items():
            revisions[kind] = step(['git', '-C', str(repo), 'rev-parse', revisions[kind] + '^{commit}'])
            bundle = stage / (kind + '.bundle')
            refs[kind] = git_bundle(repo, revisions[kind], bundle)
            add('sources/' + kind + '.bundle', bundle.read_bytes())
            # Binary tracked changes plus declared untracked source inputs.
            patch = run_group(['git', '-C', str(repo), 'diff', '--binary', revisions[kind]], timeout=60, capture=True, text=False)
            if patch.returncode:
                raise ValueError('cannot capture source patch')
            add('sources/' + kind + '.patch', patch.stdout)
            roots = data['source_inputs'][kind]
            for root in roots:
                safe_name(root)
            extra = step(['git', '-C', str(repo), 'ls-files', '--others', '--exclude-standard', '--', *roots])
            for name in extra.splitlines():
                path = repo / safe_name(name)
                if path.is_symlink() or not path.is_file():
                    raise ValueError('unsupported extra source file: ' + name)
                add('extra/' + kind + '/' + name, path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        job['elf'] = '{archive}/program.elf'
        environment = {}
        host_environment = {}
        for key, value in command.env.items():
            if key in (data['source_env'], 'RVW_HOME'):
                continue
            if key in data.get('host_environment', []):
                host_environment[key] = value
                continue
            portable = value.replace(str(repos['tools']), '{tools}').replace(str(repos['core']), '{core}')
            if os.path.isabs(portable):
                raise ValueError('nonportable replay environment: ' + key)
            environment[key] = portable
        manifest = dict(schema='rvw.portable-replay/1', revisions=revisions, refs=refs, job=job,
                        environment=environment, host_environment=host_environment, original_dirty={k: source.get(k + '_dirty') for k in repos}, failure_signature=signature(raw),
                        expected={k: raw.get(k) for k in ('core', 'config', 'status', 'cycles', 'instret', 'fail_code', 'rtl_sha256', 'elf_sha256', 'seed', 'max_cycles', 'mem_latency', 'sim_threads')},
                        files={name: dict(sha256=digest(payload), mode=mode) for name, (payload, mode) in blobs.items()})
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, sort_keys=True))
            for name, (payload, _) in blobs.items():
                archive.writestr(name, payload)
    return dict(schema='rvw.portable-replay-pack/1', archive=str(out), sha256=digest(Path(out).read_bytes()),
                revisions=revisions, checkpoint=checkpoint, bytes=Path(out).stat().st_size)


def replay(archive, out, *, timeout=600, lock=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as packed:
        manifest = json.loads(packed.read('manifest.json'))
        if manifest.get('schema') != 'rvw.portable-replay/1':
            raise ValueError('unsupported portable replay schema')
        if len(packed.namelist()) != len(manifest['files']) + 1 or set(packed.namelist()) != set(manifest['files']) | {'manifest.json'}:
            raise ValueError('unexpected replay archive members')
        # Verify every input before source checkout or execution.
        payloads = {}
        for name, record in manifest['files'].items():
            safe_name(name)
            payload = packed.read(name)
            if digest(payload) != record['sha256']:
                raise ValueError('replay archive digest mismatch: ' + name)
            payloads[name] = payload
        for name, payload in payloads.items():
            path = out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            path.chmod(manifest['files'][name]['mode'] & 0o777)
    for kind in ('tools', 'core'):
        checkout = out / kind
        checkout.mkdir()
        step(['git', 'init', '-q', str(checkout)])
        step(['git', '-C', str(checkout), 'fetch', '-q', str(out/'sources'/f'{kind}.bundle'), manifest['refs'][kind]])
        step(['git', '-C', str(checkout), 'checkout', '-q', '--detach', manifest['revisions'][kind]])
        patch = out/'sources'/f'{kind}.patch'
        if patch.stat().st_size:
            step(['git', '-C', str(checkout), 'apply', '--binary', str(patch)])
        for path in (out/'extra'/kind).rglob('*') if (out/'extra'/kind).exists() else ():
            if path.is_file():
                destination = checkout / path.relative_to(out/'extra'/kind)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(path.read_bytes()); destination.chmod(stat.S_IMODE(path.stat().st_mode))
    recipe = json.loads((out/'recipe.json').read_bytes())
    step([sys.executable, '-m', 'venv', '--without-pip', str(out/'python')], timeout=60)
    runtime_python = str(out/'python/bin/python')
    purelib = Path(step([runtime_python, '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))']))
    (purelib/'rvw-snapshot.pth').write_text(str(out/'tools/rvw/src') + '\n')
    def expand(value):
        return value.replace('{python}', runtime_python).replace('{archive}', str(out)).replace('{tools}', str(out/'tools')).replace('{core}', str(out/'core'))
    command = adapter.Command(exe=[expand(v) for v in recipe['command']], sub='run')
    for name, value in manifest['job'].items():
        command = command.set(**{name: expand(value) if isinstance(value, str) else value})
    command = command.set(out=str(out/'run'), json=True)
    env = dict(os.environ, **{key: expand(value) for key, value in manifest['environment'].items()})
    for name in manifest.get('host_environment', {}):
        if not env.get(name):
            raise ValueError('target build environment must set ' + name)
    env.update(RVW_HOME=str(out/'tools'), RVW_PYTHON=runtime_python, RVW_LOCK_PYTHON=runtime_python,
               RISCVSIM_WORK=str(out/'native'))
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env[recipe['source_env']] = str(out/'core')
    if lock and recipe.get('lock_env'):
        env[recipe['lock_env']] = lock
    result = run_group(['nice', '-n', '10', *command.argv()], env=env, timeout=timeout, capture=True, text=True)
    (out/'replay.log').write_text(result.stdout + result.stderr)
    if result.returncode not in (0, 1) or result.timed_out or not (out/'run/result.json').is_file():
        raise ValueError('portable replay did not produce a C1 result; see replay.log')
    actual = json.loads((out/'run/result.json').read_bytes())
    if RunResult.from_dict(actual).why_inconclusive:
        raise ValueError('portable replay produced inconclusive C1 evidence')
    events = trace_events(out/'run'/actual['artifacts']['rvfi_trace'])
    checkpoint = json.loads((out/'checkpoint.json').read_bytes())
    if checkpoint.get('schema') != 'rvw.portable-trace-checkpoint/1' or checkpoint.get('mode') != 'from-reset':
        raise ValueError('unsupported portable trace checkpoint')
    cycle = checkpoint['cycle']
    checks = {key: actual.get(key) == expected for key, expected in manifest['expected'].items()}
    checks['failure_signature'] = signature(actual) == manifest['failure_signature']
    checks['c2_header'] = trace_header(out/'run'/actual['artifacts']['rvfi_trace']) == json.loads((out/'expected-header.json').read_bytes())
    checks['complete_c2'] = events == json.loads((out/'expected-events.json').read_bytes())
    checks['checkpoint_prefix'] = event_digest([e for e in events if e.get('cycle', -1) < cycle]) == checkpoint['prefix_sha256']
    checks['checkpoint_suffix'] = event_digest([e for e in events if e.get('cycle', -1) >= cycle]) == checkpoint['suffix_sha256']
    report = dict(schema='rvw.portable-replay-result/1', status='reproduced' if all(checks.values()) else 'mismatch',
                  checks=checks, adapter_revision=manifest['revisions']['tools'], core_revision=manifest['revisions']['core'],
                  execution='from-reset', source_patches={kind: manifest['files']['sources/'+kind+'.patch']['sha256'] for kind in ('tools', 'core')}, result=str(out/'run/result.json'))
    (out/'replay-result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report
