"""Native identity uses stable launch inputs and hashes each tool once."""
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]


def helper(name='native-identity.py'):
    path = ROOT / 'RiscvSim/scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def native(tmp_path, monkeypatch):
    module = helper()
    for name in set(module.VARIABLES) | {k for k in os.environ if k.startswith(
            ('VERILATOR_', 'SPINAL_', 'CCACHE_', 'GCC_', 'CLANG_', 'DYLD_', 'LD_'))}:
        monkeypatch.delenv(name, raising=False)
    directory = tmp_path / 'bin'
    directory.mkdir()
    for name in ('python', 'java', 'verilator', 'clang', 'make', 'ar', 'sh', 'bash', 'perl'):
        path = directory / name
        path.write_bytes(b'\x7fELFfixture-' + name.encode())
        path.chmod(0o755)
    (directory / 'clang++').symlink_to(directory / 'clang')
    monkeypatch.setenv('PATH', str(directory))
    monkeypatch.setenv('JAVA_HOME', str(tmp_path))
    monkeypatch.setattr(module.sys, 'executable', str(directory / 'python'))
    root = tmp_path / 'verilator'
    (root / 'include').mkdir(parents=True)
    (root / 'include/verilated.mk').write_text('CXX = clang++\nLINK = clang++\n')
    probes = []

    def probe(command, **kwargs):
        probes.append(command)
        output = f'VERILATOR_ROOT = {root}\n' if command[-1] == '-V' else 'native-fixture 1.0\n'
        return SimpleNamespace(returncode=0, stdout=output, stderr='', timed_out=False)

    monkeypatch.setattr(module, 'run_group', probe)
    return SimpleNamespace(module=module, bin=directory, root=root, probes=probes)


def test_each_resolved_native_file_is_read_once(native, monkeypatch):
    opened = Counter()
    original = Path.open

    def read(path, mode='r', *args, **kwargs):
        if mode == 'rb':
            opened[str(path)] += 1
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', read)
    record = native.module.collect()
    assert record['cache_enabled'], record['cache_disabled_reasons']
    assert opened == Counter({item['path']: 1 for item in record['files']})
    assert record['tools']['compiler']['path'] == record['tools']['linker']['path']
    assert native.probes.count([record['tools']['compiler']['path'], '--version']) == 1
    assert record['provenance']['sha256'] == record['sha256']
    assert 'files' not in record['provenance']
    assert 'capture' not in record and 'file_stamps' not in record


@pytest.mark.parametrize('variable', [
    '_', 'PWD', 'OLDPWD', 'SHLVL', 'RVW_CAPTURE_INPUTS', 'RVW_CAPTURE_SOURCE',
    'RVW_LOCKS_HELD', 'RVW_LOCK_FD_BOOM', 'RVW_LOCK_PYTHON', 'RVW_PYTHON',
    'RISCVSIM_WORK', 'RISCVSIM_CP_CACHE', 'RISCVSIM_XMX', 'RISCVSIM_CACHE_ENTRIES',
])
def test_native_identity_ignores_launch_bookkeeping(native, monkeypatch, variable):
    before = native.module.collect()
    monkeypatch.setenv(variable, '/another/launch-or-elf')
    after = native.module.collect()
    assert before['sha256'] == after['sha256']
    assert before['environment_sha256'] == after['environment_sha256']


@pytest.mark.parametrize('variable,value', [
    ('SPINAL_VERILATOR_FLAGS', '-DFLAG_FAIL'), ('CXXFLAGS', '-O1'),
    ('RISCVSIM_COVERAGE', 'line'), ('UNLISTED_NATIVE_SETTING', 'changed'),
])
def test_native_identity_keeps_build_options(native, monkeypatch, variable, value):
    before = native.module.collect()
    monkeypatch.setenv(variable, value)
    after = native.module.collect()
    assert before['sha256'] != after['sha256']


def test_declared_core_checkout_selector_is_report_metadata(native, monkeypatch):
    monkeypatch.setenv('RVW_CAPTURE_SOURCE_ENV', 'MY_CORE_SOURCE')
    monkeypatch.setenv('MY_CORE_SOURCE', '/dirty-core')
    before = native.module.collect()
    monkeypatch.setenv('MY_CORE_SOURCE', '/committed-core')
    after = native.module.collect()
    assert before['sha256'] == after['sha256']
    assert 'MY_CORE_SOURCE' in after['environment_ignored']
    monkeypatch.setenv('CXXFLAGS', '-O1')
    assert native.module.collect()['sha256'] != before['sha256']


def test_undeclared_checkout_selector_still_changes_native_identity(native, monkeypatch):
    monkeypatch.delenv('RVW_CAPTURE_SOURCE_ENV', raising=False)
    monkeypatch.setenv('MY_CORE_SOURCE', '/dirty-core')
    before = native.module.collect()
    monkeypatch.setenv('MY_CORE_SOURCE', '/committed-core')
    assert native.module.collect()['sha256'] != before['sha256']


@pytest.mark.parametrize('failure', [False, True])
def test_native_launch_uses_saved_record_without_reading_tools(native, tmp_path, monkeypatch, failure):
    module = native.module
    record = module.collect()
    calls = []

    def launch(command, **kwargs):
        calls.append(command)
        assert command[0] == record['tools']['java']['path']
        assert json.loads(command[1].split('=', 1)[1]) == record
        env = kwargs['env']
        for name in ('verilator', 'make', 'ar', 'sh', 'bash', 'perl'):
            assert Path(env['RISCVSIM_PINNED_BIN'], name).resolve() == Path(record['tools'][name]['path'])
        assert Path(env['RISCVSIM_PINNED_CXX']).name == 'clang++'
        assert Path(env['RISCVSIM_PINNED_LINK']).name == 'clang++'
        if failure:
            raise RuntimeError('launch failed')
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(module, 'run_group', launch)
    monkeypatch.setattr(Path, 'open', lambda *args, **kwargs: pytest.fail('launch reread a native input'))
    if failure:
        with pytest.raises(RuntimeError, match='launch failed'):
            module.launch(record, tmp_path, ['-cp', 'classes', 'Main'])
    else:
        assert module.launch(record, tmp_path, ['-cp', 'classes', 'Main']) == 7
    assert len(calls) == 1
    assert not list(tmp_path.glob('native-bin.*'))


def test_native_verilator_backend_bytes_change_identity(native):
    backend = native.bin / 'verilator_bin'
    backend.write_bytes(b'\x7fELFbackend-one')
    backend.chmod(0o755)
    before = native.module.collect()
    backend.write_bytes(b'\x7fELFbackend-two')
    after = native.module.collect()
    assert before['tools']['verilator_bin']['version'] == after['tools']['verilator_bin']['version']
    assert before['tools']['verilator_bin']['sha256'] != after['tools']['verilator_bin']['sha256']
    assert before['sha256'] != after['sha256']
