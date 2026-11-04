"""Focused installer checks. No package installs or native builds run here."""
import os
import shlex
from pathlib import Path
from rvw.common.proc import run_group

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/install.sh'


def invoke(*args, env=None, cwd=ROOT, script=SCRIPT):
    return run_group(['bash', str(script), *map(str, args)], cwd=cwd,
                     env=env, input='', capture=True, timeout=30)


def test_help():
    result = invoke('--help')
    assert result.returncode == 0
    for flag in ('--all', '--check', '--dry-run', '--source', '--shell-rc', '--with-gem5'):
        assert flag in result.stdout


@pytest.mark.parametrize('args', [
    ['--no-such-option'], ['--prefix'], ['--source'], ['--shell-rc'],
    ['--prefix', '--yes'], ['--check', '--dry-run'], ['--source', ROOT],
    ['--prefix', 'bad\npath'],
])
def test_usage_errors(args):
    result = invoke(*args)
    assert result.returncode == 2
    assert 'install.sh:' in result.stderr


def test_dry_run_makes_no_target_or_shell_rc(tmp_path):
    target = tmp_path / 'tools with spaces'
    rc = tmp_path / 'shell rc'
    result = invoke('--prefix', target, '--source', ROOT, '--shell-rc', rc,
                    '--dry-run')
    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert not rc.exists()
    assert 'git clone --no-hardlinks' in result.stdout
    assert 'uv venv' in result.stdout
    assert 'uv sync --locked' in result.stdout
    assert 'env.sh' in result.stdout
    assert '#put-the-project-files-in-your-core-repository' in result.stdout


def test_check_missing_install_is_read_only(tmp_path):
    target = tmp_path / 'absent'
    result = invoke('--prefix', target, '--check')
    assert result.returncode == 1
    assert 'MISSING rvw venv' in result.stdout
    assert not target.exists()
    assert 'apt-get install' not in result.stdout
    assert 'brew install' not in result.stdout


def test_reject_unrelated_prefix(tmp_path):
    result = invoke('--prefix', tmp_path, '--dry-run')
    assert result.returncode == 2
    assert 'not a workstation checkout' in result.stderr


def test_native_dry_run_never_executes_package_manager(tmp_path):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    # Force missing native tools while retaining the real Python and uv.
    for name in ('java', 'javac', 'sbt', 'verilator', 'riscv64-unknown-elf-gcc',
                 'yosys', 'sby', 'yices-smt2'):
        path = binaries / name
        path.write_text('#!/bin/sh\necho missing >&2\nexit 1\n')
        path.chmod(0o755)
    for name in ('brew', 'sudo', 'apt-get', 'dnf'):
        path = binaries / name
        path.write_text(f'#!/bin/sh\necho called >> "{tmp_path}/mutations"\nexit 99\n')
        path.chmod(0o755)
    env = {**os.environ, 'PATH': f'{binaries}:{os.environ["PATH"]}'}
    env.pop('JAVA_HOME', None)
    result = invoke('--all', '--dry-run', '--prefix', tmp_path / 'install', env=env)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / 'mutations').exists()
    assert not (tmp_path / 'install').exists()
    assert 'openjdk' in result.stdout or 'jdk21' in result.stdout
    assert 'Cosim/build.sh' in result.stdout
    assert 'gem5-v25.1.0.1' in result.stdout


def test_old_python_check_fails(tmp_path):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    python = binaries / 'python3'
    python.write_text('#!/bin/sh\necho "Python 3.10.15"\n')
    python.chmod(0o755)
    fallback = binaries / 'python3.11'
    fallback.write_text(python.read_text())
    fallback.chmod(0o755)
    env = {**os.environ, 'PATH': f'{binaries}:{os.environ["PATH"]}'}
    result = invoke('--check', '--prefix', tmp_path / 'absent', env=env)
    assert result.returncode == 1
    assert 'TOO OLD Python: 3.10.15' in result.stdout


def package_environment(tmp_path):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    commands = {
        'uname': 'echo Darwin',
        'uv': 'echo "uv 0.1.0"',
        'brew': f'echo called >> "{tmp_path}/mutations"; exit 99',
    }
    for name, body in commands.items():
        path = binaries / name
        path.write_text(f'#!/bin/sh\n{body}\n')
        path.chmod(0o755)
    return {**os.environ, 'PATH': f'{binaries}:{os.environ["PATH"]}',
            'SPIKE_PREFIX': str(tmp_path / 'spike'), 'HOME': str(tmp_path)}


def test_package_command_needs_approval(tmp_path):
    env = package_environment(tmp_path)
    result = invoke('--prefix', tmp_path / 'install', env=env)
    assert result.returncode == 2
    assert 'Run this system package command?' in result.stdout
    assert 'brew install uv' in result.stdout
    assert not (tmp_path / 'mutations').exists()
    assert not (tmp_path / 'install').exists()


def test_yes_approves_displayed_package_command(tmp_path):
    env = package_environment(tmp_path)
    result = invoke('--prefix', tmp_path / 'install', '--yes', env=env)
    assert result.returncode == 99  # The fake package manager ran and failed.
    assert 'brew install uv' in result.stdout
    assert (tmp_path / 'mutations').read_text() == 'called\n'
    assert not (tmp_path / 'install').exists()


def test_unsupported_os_prints_manual_steps(tmp_path):
    env = package_environment(tmp_path)
    (tmp_path / 'bin/uname').write_text('#!/bin/sh\necho FreeBSD\n')
    result = invoke('--prefix', tmp_path / 'install', '--dry-run', env=env)
    assert result.returncode == 1
    assert 'Unsupported OS' in result.stdout
    assert 'uv venv' in result.stdout
    assert not (tmp_path / 'mutations').exists()
    assert not (tmp_path / 'install').exists()


def gem5_binary(path, version='25.1.0.1', riscv=True, code=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    output = f'gem5 version {version}\n    USE_RISCV_ISA = {riscv}\n'
    path.write_text('#!/bin/sh\n[ "$1" = --build-info ] || exit 99\n'
                    f'printf %s {shlex.quote(output)}\nexit {code}\n')
    path.chmod(0o755)
    return path


@pytest.mark.parametrize(('version', 'riscv', 'code', 'message'), [
    ('25.1.0.1', True, 0, 'PRESENT gem5: 25.1.0.1 (RISC-V)'),
    ('25.1.0.0', True, 0, 'WRONG VERSION gem5'),
    ('25.1.0.10', True, 0, 'WRONG VERSION gem5'),
    ('25.1.0.1-dev', True, 0, 'WRONG VERSION gem5'),
    ('25.1.0.1', False, 0, 'MISSING gem5 RISC-V support'),
    ('25.1.0.1', True, 1, 'UNUSABLE gem5'),
])
def test_gem5_check_exact_version_and_isa(tmp_path, version, riscv, code, message):
    binary = gem5_binary(tmp_path / 'native tools/gem5.opt', version, riscv, code)
    target = tmp_path / 'absent'
    env = {**os.environ, 'RVW_GEM5': str(binary)}
    result = invoke('--prefix', target, '--with-gem5', '--check', env=env)
    assert result.returncode == 1  # The core install is absent.
    assert message in result.stdout
    assert not target.exists()


def test_gem5_invalid_selection_refuses_before_install(tmp_path):
    target = tmp_path / 'absent'
    env = {**os.environ, 'RVW_GEM5': str(tmp_path / 'missing')}
    result = invoke('--prefix', target, '--with-gem5', '--dry-run', env=env)
    assert result.returncode == 2
    assert 'RVW_GEM5 is invalid' in result.stderr
    assert 'uv venv' not in result.stdout
    assert not target.exists()


def test_gem5_check_missing_binary_is_read_only(tmp_path):
    env = {**os.environ, 'RVW_GEM5': str(tmp_path / 'missing')}
    result = invoke('--prefix', tmp_path / 'absent', '--with-gem5', '--check', env=env)
    assert result.returncode == 1
    assert 'MISSING gem5:' in result.stdout
    assert not (tmp_path / 'absent').exists()


def test_gem5_external_reuse_dry_run(tmp_path):
    gem5_binary(tmp_path / 'native tools/gem5.opt')
    env = {**os.environ, 'RVW_GEM5': 'native tools/gem5.opt'}
    result = invoke('--prefix', tmp_path / 'absent', '--with-gem5', '--dry-run',
                    env=env, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert f'(RISC-V) {tmp_path}/native tools/gem5.opt' in result.stdout
    assert 'gem5/gem5.git' not in result.stdout
    assert 'defconfig' not in result.stdout
    assert 'protobuf' not in result.stdout
    assert not (tmp_path / 'absent').exists()


def test_gem5_managed_reuse_dry_run(tmp_path):
    target = tmp_path / 'workstation'
    binary = gem5_binary(target / '.tools/src/gem5-v25.1.0.1/build/RISCV/gem5.opt')
    for name in ('rvw/pyproject.toml', 'Cosim/build.sh'):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    env = {**os.environ}
    env.pop('RVW_GEM5', None)
    result = invoke('--prefix', target, '--with-gem5', '--dry-run', env=env)
    assert result.returncode == 0, result.stderr
    assert f'(RISC-V) {binary}' in result.stdout
    assert 'defconfig' not in result.stdout
    assert 'protobuf' not in result.stdout
    assert not (target / 'env.sh').exists()


@pytest.mark.parametrize(('system', 'distro', 'dependencies'), [
    ('Darwin', '', 'brew install python@3.14 protobuf gperftools libpng pkgconf zlib m4'),
    ('Linux', 'ubuntu', 'build-essential python3-dev python3-venv zlib1g-dev'),
    ('Linux', 'fedora', 'gcc gcc-c++ make python3-devel zlib-devel'),
])
def test_gem5_native_build_plan(tmp_path, system, distro, dependencies):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    for name, body in {
        'uname': f'echo {system}',
        'uv': 'echo "uv 0.13.6"',
        'xcrun': 'exit 0',
        **{name: f'echo called >> "{tmp_path}/mutations"; exit 99'
           for name in ('brew', 'sudo', 'apt-get', 'dnf')},
    }.items():
        path = binaries / name
        path.write_text(f'#!/bin/sh\n{body}\n')
        path.chmod(0o755)
    release = tmp_path / 'os-release'
    release.write_text(f'ID={distro}\n')
    script = tmp_path / 'install.sh'
    script.write_text(SCRIPT.read_text().replace('/etc/os-release', str(release)))
    env = {**os.environ, 'PATH': f'{binaries}:{os.environ["PATH"]}',
           'HOME': str(tmp_path), 'SPIKE_PREFIX': str(tmp_path / 'spike')}
    env.pop('RVW_GEM5', None)
    target = tmp_path / 'absent with spaces'
    result = invoke('--prefix', target, '--with-gem5', '--dry-run', env=env, script=script)
    assert result.returncode == 0, result.stderr
    assert dependencies in result.stdout
    assert '--branch v25.1.0.1' in result.stdout
    assert 'c8222cc67a399bfc01e8658dd14b30d5bfd634f9' in result.stdout
    assert 'gem5-venv/bin/scons' in result.stdout
    assert 'defconfig ' in result.stdout
    assert 'gem5-v25.1.0.1/build_opts/RISCV --ignore-style' in result.stdout
    assert 'with-lock.sh gem5 nice' in result.stdout
    assert 'build/RISCV/gem5.opt -j2 --ignore-style' in result.stdout
    assert 'docker' not in result.stdout.lower()
    assert not target.exists()
    assert not (tmp_path / 'mutations').exists()


@pytest.mark.parametrize(('revision', 'dirty'), [
    ('wrong-commit', 0),
    ('c8222cc67a399bfc01e8658dd14b30d5bfd634f9', 1),
    ('c8222cc67a399bfc01e8658dd14b30d5bfd634f9', 0),
])
def test_gem5_source_checks_and_build_failure(tmp_path, revision, dirty):
    target = tmp_path / 'workstation'
    for name in ('rvw/pyproject.toml', 'Cosim/build.sh'):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (target / '.tools/src/gem5-v25.1.0.1/.git').mkdir(parents=True)
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    commands = {
        'uname': 'echo Linux',
        'python3': 'case "$*" in --version) echo "Python 3.11.0";; '
                   f'"-I -c"*) echo {shlex.quote(str(binaries / "base-python3"))};; *) exit 99;; esac',
        'base-python3-config': 'exit 0',
        'uv': 'echo "uv 0.13.6"',
        'apt-get': 'exit 0',
        'sudo': 'exec "$@"',
        'git': f'case "$*" in *"rev-parse HEAD") echo {revision};; '
               f'*"diff --quiet HEAD --") exit {dirty};; *) exit 99;; esac',
    }
    for name, body in commands.items():
        path = binaries / name
        path.write_text(f'#!/bin/sh\n{body}\n')
        path.chmod(0o755)
    lock = target / 'scripts/with-lock.sh'
    lock.parent.mkdir(parents=True)
    lock.write_text('#!/bin/sh\n[ "$1" = gem5 ] || exit 99\nshift\nexec "$@"\n')
    lock.chmod(0o755)
    scons = target / '.tools/gem5-venv/bin/scons'
    scons.parent.mkdir(parents=True)
    scons.write_text('#!/bin/sh\n'
                     f'[ "$PYTHON_CONFIG" = {shlex.quote(str(binaries / "base-python3-config"))} ] || exit 99\n'
                     f'printf "%s\\n" "$@" > {shlex.quote(str(tmp_path / "scons-args"))}\nexit 17\n')
    scons.chmod(0o755)
    release = tmp_path / 'os-release'
    release.write_text('ID=ubuntu\n')
    script = tmp_path / 'install.sh'
    script.write_text(SCRIPT.read_text().replace('/etc/os-release', str(release)))
    env = {**os.environ, 'PATH': f'{binaries}:{os.environ["PATH"]}',
           'HOME': str(tmp_path), 'SPIKE_PREFIX': str(tmp_path / 'spike')}
    env.pop('RVW_GEM5', None)
    result = invoke('--prefix', target, '--with-gem5', '--yes', env=env, script=script)
    if revision == 'wrong-commit' or dirty:
        assert result.returncode == 2, result.stderr
        assert 'gem5 source must be clean at c8222cc' in result.stderr
        assert 'with-lock.sh gem5' not in result.stdout
        assert not (tmp_path / 'scons-args').exists()
    else:
        assert result.returncode == 17, result.stderr
        source = target / '.tools/src/gem5-v25.1.0.1'
        assert (tmp_path / 'scons-args').read_text().splitlines() == [
            '-C', str(source), 'defconfig', str(source / 'build/RISCV'),
            str(source / 'build_opts/RISCV'), '--ignore-style',
        ]
    assert not (target / 'env.sh').exists()


def test_installer_uses_locked_inputs():
    script = SCRIPT.read_text()
    assert 'uv sync --locked' in script
    assert 'releases/latest' not in script
    assert 'assets/latest' not in script
    assert 'submodule update --init --recursive' in script
    assert 'verify_archive' in script
    assert (ROOT / 'rvw/uv.lock').is_file()


@pytest.mark.parametrize('version', ['5.049', '5.999'])
def test_untested_verilator_warns(tmp_path, version):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    tool = binaries / 'verilator'
    tool.write_text(f'#!/bin/sh\necho "Verilator {version}"\n')
    tool.chmod(0o755)
    env = {**os.environ, 'PATH': f'{binaries}:{os.environ["PATH"]}'}
    result = invoke('--check', '--with-sim', '--prefix', tmp_path / 'absent', env=env)
    assert f'WARNING Verilator {version}' in result.stdout
    if version == '5.049':
        assert 'FSM coverage' in result.stdout


def test_waves_installer_requires_lock():
    script = (ROOT / 'SpinalWaves/scripts/install.sh').read_text()
    for line in script.splitlines():
        if line.strip().startswith(('cargo build ', 'cargo test ')):
            assert '--locked' in line


@pytest.mark.parametrize('correct', [False, True])
def test_archive_checksum_is_enforced(tmp_path, correct):
    import hashlib
    import sys
    archive = tmp_path / 'archive'
    archive.write_bytes(b'archive input')
    expected = hashlib.sha256(archive.read_bytes()).hexdigest() if correct else '0' * 64
    text = SCRIPT.read_text()
    function = text[text.index('verify_archive() {'):text.index('pinned_source() {')]
    wrapper = ('set -e\ndry=0\nrun() { "$@"; }\n' + function
               + '\nverify_archive "$1" "$2"\n')
    result = run_group(['bash', '-c', wrapper, '_', str(archive), expected],
                       env={**os.environ, 'RVW_PYTHON': sys.executable}, capture=True, timeout=10)
    assert (result.returncode == 0) == correct
    if not correct:
        assert 'checksum mismatch' in result.stderr


def test_pinned_sources_include_recorded_submodules(tmp_path):
    text = SCRIPT.read_text()
    function = text[text.index('pinned_source() {'):text.index('# Use this archive')]
    wrapper = ('dry=1\nrun() { printf "%s " "$@"; printf "\\n"; }\n' + function
               + '\npinned_source https://example.invalid/repo "$1" deadbeef\n')
    result = run_group(['bash', '-c', wrapper, '_', str(tmp_path / 'source')],
                       capture=True, timeout=10)
    assert result.returncode == 0
    assert 'submodule update --init --recursive' in result.stdout


def test_installer_workflow_passes_actionlint():
    import shutil
    actionlint = shutil.which('actionlint')
    if not actionlint:
        pytest.skip('actionlint is not installed')
    result = run_group([actionlint, '.github/workflows/installer.yml'],
                       cwd=ROOT, capture=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_spike_pin_matches_qualified_reference():
    script = SCRIPT.read_text()
    assert 'spike_revision=eff659cd43d7eafb7f3559bceed2540eabb31c50' in script
    assert 'spike-source.json' in script
    assert '--without-boost --without-boost-asio --without-boost-regex' in script


def test_macos_cosim_uses_same_source_pin(tmp_path):
    env = package_environment(tmp_path)
    result = invoke('--prefix', tmp_path / 'install', '--with-cosim', '--dry-run', env=env)
    assert result.returncode == 0, result.stderr
    assert 'eff659cd43d7eafb7f3559bceed2540eabb31c50' in result.stdout
    assert 'make -C' in result.stdout
    assert 'brew install riscv-software-src/riscv/riscv-isa-sim' not in result.stdout


def test_bundle_needs_explicit_location(tmp_path):
    result = invoke('--from-bundle', '--with-riscv-gcc', '--prefix', tmp_path / 'absent')
    assert result.returncode == 2
    assert '--bundle-run or --bundle-dir' in result.stderr
    assert not (tmp_path / 'absent').exists()


def test_bundle_dry_run_does_not_download(tmp_path):
    result = invoke('--from-bundle', '--bundle-run', '1234', '--with-riscv-gcc',
                    '--dry-run', '--prefix', tmp_path / 'absent')
    assert result.returncode == 0, result.stderr
    assert 'native-bundle.py install' in result.stdout
    assert '--tool gcc' in result.stdout
    assert not (tmp_path / 'absent').exists()


def test_bundle_check_needs_no_run_or_network(tmp_path):
    result = invoke('--from-bundle', '--check', '--with-sail', '--prefix', tmp_path / 'absent',
                    env={**os.environ, 'RVW_SAIL': ''})
    assert result.returncode == 1
    assert 'MISSING Sail' in result.stdout
    assert 'native-bundle.py' not in result.stdout
    assert not (tmp_path / 'absent').exists()


def test_formal_dry_run_builds_pinned_native_slang(tmp_path):
    env = {**os.environ, 'RVW_SLANG': str(tmp_path / 'absent.so')}
    result = invoke('--with-formal', '--dry-run', '--prefix', tmp_path / 'install', env=env)
    assert result.returncode == 0, result.stderr
    assert 'build-yosys-slang.py' in result.stdout
    assert '--yosys-config' in result.stdout
    assert not (tmp_path / 'install').exists()


def test_slang_checksum_error_precedes_build(tmp_path):
    import json
    source = json.loads((ROOT / 'scripts/yosys-slang-sources.json').read_text())[0]
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    (downloads / (source['name'] + '-' + source['revision'] + '.tar.gz')).write_bytes(b'changed')
    result = run_group([str(ROOT / 'rvw/.venv/bin/python'),
                        str(ROOT / 'scripts/build-yosys-slang.py'), '--prefix', str(tmp_path),
                        '--yosys-config', '/unused/yosys-config'], capture=True, timeout=10)
    assert result.returncode != 0
    assert 'archive checksum mismatch' in result.stderr
    assert not (tmp_path / 'src').exists()
    assert not (tmp_path / 'build').exists()


def test_typed_waves_dry_run_uses_dedicated_package(tmp_path):
    target = tmp_path / 'typed install'
    result = invoke('--with-typed-waves', '--dry-run', '--prefix', target)
    assert result.returncode == 0, result.stderr
    assert 'SpinalWaves/scripts/install.sh' in result.stdout
    assert '--copy' in result.stdout
    assert str(target).replace(' ', r'\ ') + '/.tools/bin' in result.stdout
    assert not target.exists()


def test_typed_waves_check_refuses_missing_viewer(tmp_path):
    result = invoke('--with-typed-waves', '--check', '--prefix', tmp_path / 'absent')
    assert result.returncode == 1
    assert 'MISSING typed viewer' in result.stdout
    assert not (tmp_path / 'absent').exists()
