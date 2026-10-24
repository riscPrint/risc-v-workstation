"""Interpreter bindings must work without a usable python3 on PATH."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

from race_injection import race_injector
from rvw.common.proc import run_group
from test_riscvsim_scripts import launcher

ROOT = Path(__file__).resolve().parents[2]


def broken_python(directory):
    path = directory / 'python3'
    path.write_text('#!/bin/sh\necho unexpected-PATH-python3 >&2\nexit 97\n')
    path.chmod(0o755)
    return path


@pytest.mark.parametrize('fallback', [False, True])
def test_identity_uses_selected_python_with_broken_path(launcher, fallback):
    broken_python(launcher.bin)
    env = {**launcher.env, 'RVW_PYTHON': sys.executable}
    if fallback:
        env.pop('RVW_PYTHON')
        venv = launcher.sim.parent / '.venv/bin'
        venv.mkdir(parents=True)
        (venv / 'python').symlink_to(sys.executable)
    result = run_group([str(launcher.sim / 'boom/run.sh'), 'identity'],
                       env=env, capture=True, timeout=30)
    native = json.loads(next(line.removeprefix('native-build ') for line in result.stdout.splitlines()
                             if line.startswith('native-build ')))
    assert result.returncode == 0, (result.stderr, native['cache_disabled_reasons'])
    assert native['tools']['python']['path'] == str(Path(sys.executable).resolve())
    assert any(item['path'] == native['tools']['python']['path']
               for item in native['tools'].values())
    assert 'unexpected-PATH-python3' not in result.stderr


@pytest.mark.parametrize('fallback', [False, True])
def test_lock_uses_selected_python_with_broken_path(tmp_path, fallback):
    import shutil
    bin_ = tmp_path / 'bin'
    bin_.mkdir()
    broken_python(bin_)
    script = tmp_path / 'scripts/with-lock.sh'
    script.parent.mkdir()
    shutil.copy2(ROOT / 'scripts/with-lock.sh', script)
    helper = tmp_path / 'rvw/src/rvw/common/lock.py'
    helper.parent.mkdir(parents=True)
    shutil.copy2(ROOT / 'rvw/src/rvw/common/lock.py', helper)
    env = {**os.environ, 'PATH': str(bin_) + os.pathsep + os.environ['PATH'],
           'RVW_LOCK_PYTHON': sys.executable, 'RVW_LOCK_DIR': str(tmp_path / 'locks')}
    env.pop('RVW_LOCKS_HELD', None)
    if fallback:
        env.pop('RVW_LOCK_PYTHON')
        venv = tmp_path / 'rvw/.venv/bin'
        venv.mkdir(parents=True)
        (venv / 'python').symlink_to(sys.executable)
    result = run_group([str(script), 'python-binding-test', '/usr/bin/true'],
                       env=env, capture=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert 'unexpected-PATH-python3' not in result.stderr


def test_missing_direct_python_refuses_before_path_lookup(launcher):
    broken_python(launcher.bin)
    env = dict(launcher.env)
    env.pop('RVW_PYTHON', None)
    result = run_group([str(launcher.sim / 'boom/run.sh'), 'identity'],
                       env=env, capture=True, timeout=15)
    assert result.returncode != 0
    assert 'RVW_PYTHON' in result.stderr and 'unexpected-PATH-python3' not in result.stderr


def test_build_uses_selected_python_with_broken_path(launcher):
    broken_python(launcher.bin)
    build = launcher()
    out, err = build.communicate(timeout=30)
    assert build.returncode == 0, (out, err)
    assert 'unexpected-PATH-python3' not in err
    assert not list(launcher.cache.glob('classpath-*'))


def test_regression_child_gets_captured_interpreter(fake, tmp_path, monkeypatch):
    from test_regress_capture import setup_runner
    monkeypatch.setenv('RVW_PYTHON', '/untrusted/replay/python')
    monkeypatch.setenv('RVW_LOCK_PYTHON', '/untrusted/lock/python')
    runner, plan = setup_runner(fake, tmp_path / 'out')
    expected = str(Path(sys.executable).absolute())  # keep this venv interpreter path
    assert expected not in ('/untrusted/replay/python', '/untrusted/lock/python')
    assert runner.env['RVW_PYTHON'] == runner.env['RVW_LOCK_PYTHON'] == expected
    assert runner.run(plan)['ok']


def test_debug_child_gets_captured_interpreter(tmp_path, monkeypatch):
    from rvw.runs.adapter import Command
    from rvw.runs.inputs import DebugInputs
    adapter_dir = tmp_path / 'adapter'  # the adapter's folder is captured (round 23); keep the capture outside it
    adapter_dir.mkdir()
    script = adapter_dir / 'adapter.sh'
    script.write_text('#!/bin/sh\nexit 0\n')
    script.chmod(0o755)
    from rvw.common.capture import Capture
    monkeypatch.setattr('rvw.runs.inputs.new_capture', lambda out=None: Capture(tmp_path / 'capture'))
    inputs = DebugInputs()
    cmd = inputs.bind_adapter(Command(exe=[str(script)], env={'RVW_PYTHON': '/old/python'}))
    # The captured interpreter is this test's own Python (a venv keeps its own path), never the caller's value.
    assert cmd.env['RVW_PYTHON'] == cmd.env['RVW_LOCK_PYTHON'] != '/old/python'
    assert Path(cmd.env['RVW_PYTHON']).resolve() == Path(sys.executable).resolve()
    assert any(cmd.env['RVW_PYTHON'] in (t['path'], t.get('source')) for t in inputs.capture.record()['tools'])
    inputs.verify()


def test_native_collection_keeps_selected_interpreter(launcher, tmp_path, monkeypatch):
    from test_native_identity import helper
    module = helper()
    executable = tmp_path / 'selected-python'
    executable.write_text('#!/bin/sh\necho Python-fixture\n')
    executable.chmod(0o755)
    monkeypatch.setattr(module.sys, 'executable', str(executable))
    for name, value in launcher.env.items():
        monkeypatch.setenv(name, value)
    record = module.collect()
    assert record['tools']['python']['path'] == str(executable)
    assert any(item['path'] == str(executable) for item in record['files'])
