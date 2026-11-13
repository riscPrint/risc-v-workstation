"""Project-owned ACT4 builds. Expected signatures come only from Sail."""
from collections import Counter
from hashlib import sha256
import json
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
    versions = data['extensions']
    allowed = wanted | {'sm'} | {m.lower() for m in platform.privilege_modes if m != 'M'}
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
    if len(platform.ram) != 1 or platform.reset_pc != platform.ram[0][0]:
        raise ValueError('ACT4 requires one RAM range beginning at reset_pc')
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
    return dict(schema='rvw.act4-plan/1', isa=platform.isa,
                privilege_modes=platform.privilege_modes, extensions=selected,
                limitations=data.get('limits', []),
                test_selection='all-applicable' if data.get('all_applicable') else 'extensions',
                include_priv_tests=data.get('include_priv_tests', bool(data.get('all_applicable'))),
                evidence='selection only; no DUT execution')


def build(profile, checkout, out, timeout=900, compiler='riscv64-unknown-elf-gcc',
          reference='sail_riscv_sim'):
    data, platform, selected = description(profile)
    checkout, out = Path(checkout).resolve(), Path(out).resolve()
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
    udb = dict(kind='architecture configuration', type='fully configured', name='rvw-act4',
               description='Project ACT4 profile', implemented_extensions=[
                   dict(name=data.get('udb_names', {}).get(k, k.upper() if len(k) == 1 else k[0].upper()+k[1:]), version=v)
                   for k, v in data['extensions'].items()], params=data['params'])
    # JSON is valid YAML and avoids a second serializer and implicit YAML types.
    (config / 'udb.yaml').write_text(json.dumps(udb, indent=2))
    tc = dict(name='rvw-act4', compiler_exe=compiler, ref_model_exe=reference,
              udb_config='udb.yaml', linker_script='link.ld', dut_include_dir='.',
              include_priv_tests=data.get('include_priv_tests', bool(data.get('all_applicable'))))
    (config / 'test_config.yaml').write_text(json.dumps(tc, indent=2))
    cmd = ['make', '-C', str(checkout), f'CONFIG_FILES={config / "test_config.yaml"}',
           f'WORKDIR={out / "work"}', 'JOBS=2', 'FAST=True', 'EXCLUDE_EXTENSIONS=']
    if data.get('all_applicable'):
        cmd += ['EXTENSIONS=']
    else:
        cmd += ['EXTENSIONS=' + ','.join(data.get('udb_names', {}).get(x, x.upper() if len(x)==1 else x[0].upper()+x[1:]) for x in selected)]
    with (out / 'build.log').open('w') as log:
        result = run_group(cmd, timeout=timeout, stdout=log, stderr=log)
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
                    reference=reference, compiler=compiler, tools=tools, signatures=signatures, selection=selection(profile),
                    files={n: digest(config / n) for n in ('rvmodel_macros.h', 'sail.json', 'link.ld', 'udb.yaml')},
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
