"""Project-owned ACT4 builds. Expected signatures come only from Sail."""
from collections import Counter
from hashlib import sha256
import json
import os
import platform as host_platform
from pathlib import Path
import shutil

from rvw.common.proc import run_group
from rvw.cosim.platform import Platform
from rvw.cosim.sail_config import isa_extensions


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def description(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    if data.get('schema') != 'rvw.act4/1':
        raise ValueError('expected rvw.act4/1')
    root = path.parent
    platform = Platform.load(None, root / data['platform'])
    wanted = isa_extensions(platform.isa, platform.xlen)
    reference = isa_extensions(platform.reference_isa or platform.isa, platform.xlen)
    versions = data['extensions']
    allowed = wanted | reference | {'sm'} | {m.lower() for m in platform.privilege_modes if m != 'M'}
    # Privileged option extensions are explicit project settings, never inferred from a core name.
    allowed |= set(data.get('privileged_extensions', []))
    if not wanted - {'zmmul', 'zaamo', 'zalrsc', 'zca', 'zcf', 'zcd'} <= set(versions):
        raise ValueError('declare all platform ISA extensions in ACT4')
    required = {'i', 'sm'} | {m.lower() for m in platform.privilege_modes if m != 'M'}
    if set(versions) - allowed or not required <= set(versions):
        raise ValueError('ACT4 extensions contradict the platform ISA or privilege declaration')
    if any(not isinstance(v, str) or not v for v in versions.values()):
        raise ValueError('declare an ACT4/UDB version for each extension')
    if set(data.get('privileged_extensions', [])) and 'S' not in platform.privilege_modes:
        raise ValueError('privileged extensions require supervisor support')
    if data['halt'] != 'tohost-1-3':
        raise ValueError('only tohost pass=1/fail=3 is supported')
    if len(platform.ram) != 1 or not (platform.ram[0][0] <= platform.reset_pc < sum(platform.ram[0])):
        raise ValueError('ACT4 requires one RAM range containing reset_pc')
    if data['params']['MXLEN'] != platform.xlen:
        raise ValueError('ACT4 MXLEN differs from platform')
    if data.get('all_applicable') and 'test_extensions' in data:
        raise ValueError('all_applicable and test_extensions are mutually exclusive')
    selected = data.get('test_extensions', [x for x in versions if data.get('all_applicable') or x not in ('sm', 's', 'u')])
    if not selected or set(selected) - set(versions):
        raise ValueError('test_extensions must be a nonempty subset of declared extensions')
    return data, platform, selected


def selection(profile):
    data, platform, selected = description(profile)
    from .act4_csr import csr_contract
    contract = csr_contract(profile, data, platform)
    return dict(schema='rvw.act4-plan/1', isa=platform.isa, csr_contract=contract,
                privilege_modes=platform.privilege_modes, extensions=selected,
                limitations=data.get('limits', []),
                test_selection='all-applicable' if data.get('all_applicable') else 'extensions',
                include_priv_tests=data.get('include_priv_tests', bool(data.get('all_applicable'))),
                evidence='selection only; no DUT execution')


def architecture_config(data):
    """Bind UDB's named configuration cache to the actual architecture."""
    value = dict(kind='architecture configuration', type='fully configured', name='rvw-act4',
               description='Project ACT4 profile', implemented_extensions=[
                   dict(name=data.get('udb_names', {}).get(k, k.upper() if len(k) == 1 else k[0].upper()+k[1:]), version=v)
                   for k, v in data['extensions'].items()], params=data['params'])
    key = sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:20]
    value["name"] = "rvw-act4-" + key
    return value


def prepare_host(checkout, cache):
    """Use a captured macOS Z3 library in a private UDB cache."""
    env = os.environ.copy()
    if host_platform.system() != 'Darwin':
        return env, None
    brew = run_group(['brew', '--prefix', 'z3'], timeout=30, capture=True)
    if brew.returncode or brew.timed_out:
        raise RuntimeError('ACT4 on macOS needs Homebrew z3')
    library = Path(brew.stdout.strip()) / 'lib/libz3.dylib'
    # Read the installed gem's pin without loading its Linux Z3 library.
    query = "s=Gem::Specification.find_by_name('udb'); puts File.read(File.join(s.full_gem_path,'lib/udb/Z3_VERSION')).strip"
    env['BUNDLE_GEMFILE'] = str(Path(checkout).resolve() / 'framework/src/act/data/Gemfile')
    env['MISE_TRUSTED_CONFIG_PATHS'] = str(Path(checkout).resolve())
    env['BUNDLE_FROZEN'] = 'true'
    ready = run_group(['mise', 'exec', '--no-deps', '--', 'bundle', 'check'], cwd=checkout,
                      timeout=60, capture=True, env=env)
    if ready.returncode or ready.timed_out:
        installed = run_group(['mise', 'exec', '--no-deps', '--', 'bundle', 'install', '--jobs', '2'],
                              cwd=checkout, timeout=300, capture=True, env=env)
        if installed.returncode or installed.timed_out:
            raise RuntimeError('ACT4 locked Ruby setup failed: ' + (installed.stderr or 'timeout'))
    gem = run_group(['mise', 'exec', '--no-deps', '--', 'bundle', 'exec', 'ruby', '-e', query], cwd=checkout,
                    timeout=60, capture=True, env=env)
    version = (gem.stdout or '').strip()
    import re
    if gem.returncode or gem.timed_out or not re.fullmatch(r'z3-[0-9.]+', version):
        raise RuntimeError('cannot read the installed ACT4 UDB Z3 version: ' + (gem.stderr or version or 'timeout'))
    cpu = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64'}.get(host_platform.machine())
    if not cpu:
        raise RuntimeError('unsupported macOS ACT4 host CPU')
    identity = dict(path=str(library.resolve()), sha256=digest(library), udb_z3_version=version)
    dest = Path(cache) / 'udb/z3' / version / cpu
    dest.mkdir(parents=True)
    # Both names are used by the UDB loader and the Ruby z3 gem.
    shutil.copyfile(library, dest / 'libz3.so')
    (dest / 'libz3.dylib').symlink_to('libz3.so')
    env.setdefault('UV_CACHE_DIR', str(Path.home() / '.cache/uv'))
    env.setdefault('MISE_CACHE_DIR', str(Path.home() / '.cache/mise'))
    env['XDG_CACHE_HOME'] = str(Path(cache).resolve())
    return env, identity


def build(profile, checkout=None, out=None, timeout=900, compiler='riscv64-unknown-elf-gcc',
          reference=None):
    data, platform, selected = description(profile)
    plan = selection(profile)
    from rvw.common.dependencies import resolve
    if out is None:
        raise ValueError('ACT4 build requires out')
    if checkout is None:
        checkout = resolve('act4', acquire=True, revision=data['revision'])['path']
    if reference is None:
        reference = resolve('sail', acquire=True)['path']
    checkout, out = Path(checkout).resolve(), Path(out).resolve()
    if out == checkout or checkout in out.parents:
        raise ValueError('ACT4 output must be outside the source checkout')
    rev = run_group(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], timeout=30, capture=True)
    if rev.returncode or rev.stdout.strip() != data['revision']:
        raise ValueError('ACT4 checkout revision differs from the pinned project revision')
    dirty = run_group(['git', '-C', str(checkout), 'status', '--porcelain', '--untracked-files=no'], timeout=30, capture=True)
    if dirty.returncode or dirty.stdout.strip():
        raise ValueError('ACT4 tracked sources must be clean')
    out.mkdir(parents=True, exist_ok=False)
    config = out / 'config'
    config.mkdir()
    source = Path(profile).resolve().parent
    for name in ('rvmodel_macros.h', 'sail.json', 'link.ld'):
        shutil.copyfile(source / data['files'][name], config / name)
    # All platform-dependent UDB options are project data. No generic defaults hide a mismatch.
    udb = architecture_config(data)
    # JSON is valid YAML and avoids a second serializer and implicit YAML types.
    (config / 'udb.yaml').write_text(json.dumps(udb, indent=2))
    tc = dict(name='rvw-act4', compiler_exe=compiler, ref_model_exe=reference,
              udb_config='udb.yaml', linker_script='link.ld', dut_include_dir='.',
              include_priv_tests=data.get('include_priv_tests', bool(data.get('all_applicable'))))
    (config / 'test_config.yaml').write_text(json.dumps(tc, indent=2))
    cmd = ['make', '-C', str(out / 'source'), f'CONFIG_FILES={config / "test_config.yaml"}',
           f'WORKDIR={out / "work"}', 'JOBS=2', 'FAST=True', 'EXCLUDE_EXTENSIONS=']
    if data.get('all_applicable'):
        cmd += ['EXTENSIONS=']
    else:
        cmd += ['EXTENSIONS=' + ','.join(data.get('udb_names', {}).get(x, x.upper() if len(x)==1 else x[0].upper()+x[1:]) for x in selected)]
    # Build tools can write dependencies and generated files into the source tree.
    # Exclude Git metadata so no private build can write through to managed Git storage.
    shutil.copytree(checkout, out / 'source', symlinks=False,
                    ignore=shutil.ignore_patterns('.git'))
    env, host = prepare_host(out / 'source', out / 'host-cache')
    with (out / 'build.log').open('w') as log:
        result = run_group(cmd, timeout=timeout, stdout=log, stderr=log, env=env)
    elfs = out / 'work' / 'rvw-act4' / 'elfs'
    records = [dict(path=p.relative_to(elfs).as_posix(), sha256=digest(p)) for p in sorted(elfs.rglob('*.elf'))]
    tools = {}
    for name, executable in [('compiler', compiler), ('reference', reference)]:
        resolved = shutil.which(executable)
        version = run_group([executable, '--version'], timeout=30, capture=True)
        tools[name] = dict(executable=executable, sha256=digest(resolved) if resolved else None,
                           version=(version.stdout or version.stderr or '').splitlines()[:1])
    signatures = {p.relative_to(out).as_posix(): digest(p) for p in sorted((out / 'work').rglob('*.sig'))}
    manifest = dict(schema='rvw.act4-build/1', status='built' if result.returncode == 0 and records else 'error',
                    revision=data['revision'], profile_sha256=digest(profile), command=cmd,
                    reference=reference, compiler=compiler, host=host, tools=tools, signatures=signatures, selection=plan,
                    files={n: digest(config / n) for n in ('rvmodel_macros.h', 'sail.json', 'link.ld', 'udb.yaml')},
                    csr_model_sha256=digest(source / data['csr_model']) if 'csr_model' in data else None,
                    tests=records, counts=dict(Counter(Path(r['path']).parent.name for r in records)))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def verify_manifest(path, elf_dir):
    manifest = json.loads(Path(path).read_text())
    if manifest.get('schema') != 'rvw.act4-build/1' or manifest.get('status') != 'built' or not manifest.get('tests'):
        raise ValueError('ACT4 build is absent, incomplete or failed')
    expected = {row['path']: row['sha256'] for row in manifest['tests']}
    actual = {p.relative_to(elf_dir).as_posix(): digest(p) for p in Path(elf_dir).rglob('*.elf')}
    if actual != expected:
        raise ValueError('ACT4 ELF set or hashes differ from the build manifest')
