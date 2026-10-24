"""Debug adapters keep the Python environment selected by their launch command."""
import os
from itertools import count
from pathlib import Path
import sys
import venv

import pytest

from rvw.common.capture import Capture, CaptureError
from rvw.common.proc import run_group
from rvw.runs.adapter import Command
from rvw.runs.inputs import DebugInputs


@pytest.fixture
def python_adapter(tmp_path, monkeypatch):
    identifiers = count()
    monkeypatch.setattr('rvw.runs.inputs.new_capture',
                        lambda: Capture(tmp_path / f'capture-{next(identifiers)}'))
    environment = tmp_path / 'environment'
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    python = environment / 'bin/python'
    packages = environment / f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'
    (packages / 'adapter_package.py').write_text('MARKER = "venv package"\n')
    metadata = packages / 'adapter_package-1.0.dist-info'
    metadata.mkdir()
    (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: adapter-package\nVersion: 1.0\n')
    script = tmp_path / 'adapter/adapter.py'
    script.parent.mkdir()
    script.write_text(f'#!{python}\nimport adapter_package\nprint(adapter_package.MARKER)\n')
    script.chmod(0o755)
    return python, script


@pytest.mark.parametrize('launch', ['shebang', 'env', 'explicit'])
def test_debug_adapter_preserves_venv(python_adapter, monkeypatch, launch):
    python, script = python_adapter
    if launch == 'env':
        script.write_text(script.read_text().replace(f'#!{python}', '#!/usr/bin/env python'))
        monkeypatch.setenv('PATH', str(python.parent) + os.pathsep + os.environ['PATH'])
    inputs = DebugInputs()
    command = inputs.bind_adapter(Command(exe=[str(python), str(script)] if launch == 'explicit' else [str(script)]))
    result = run_group(command.argv(), env=command.child_environment(), capture=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'venv package\n'
    assert command.exe[0] == str(python)
    assert command.env['RVW_LOCK_PYTHON'] == sys.executable
    assert any(['adapter-package', '1.0'] in item['packages']
               for item in inputs.record()['python_environments'])
    inputs.verify()


def test_debug_venv_config_change_refuses(python_adapter):
    python, script = python_adapter
    inputs = DebugInputs()
    inputs.bind_adapter(Command(exe=[str(script)]))
    config = python.parent.parent / 'pyvenv.cfg'
    config.write_text(config.read_text() + '\n# changed\n')
    with pytest.raises(CaptureError, match='input_not_captured'):
        inputs.verify()


def test_worker_keeps_launcher_venv(python_adapter, monkeypatch):
    python, script = python_adapter
    monkeypatch.setattr('rvw.runs.inputs.sys.executable', str(python))
    inputs = DebugInputs()
    command = inputs.bind_adapter(Command(exe=[str(script)]))
    assert command.env['RVW_PYTHON'] == command.env['RVW_LOCK_PYTHON'] == str(python)
    assert any(['adapter-package', '1.0'] in item['packages']
               for item in inputs.record()['python_environments'])


@pytest.mark.parametrize('launch', ['shebang', 'interpreter', 'executable'])
def test_debug_adapter_uses_replay_environment(python_adapter, monkeypatch, launch):
    python, script = python_adapter
    script.write_text(script.read_text().replace(f'#!{python}', '#!/usr/bin/env python'))
    inherited_path = os.environ['PATH']
    monkeypatch.setenv('PYTHONPATH', '/unused/server/packages')
    replay_path = os.pathsep.join((str(python.parent), str(script.parent), inherited_path))
    exe = {'shebang': [str(script)], 'interpreter': ['python', str(script)],
           'executable': [script.name]}[launch]
    inputs = DebugInputs()
    command = inputs.bind_adapter(Command(exe=exe, env={'PATH': replay_path},
                                           unset=['PATH', 'PYTHONPATH']))
    result = run_group(command.argv(), env=command.child_environment(), capture=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'venv package\n'
    assert command.exe[0] == str(python)
    assert command.env['RVW_PYTHON'] == command.env['RVW_LOCK_PYTHON'] == sys.executable
    assert os.environ['PATH'] == inherited_path
    assert any(item['path'] == str(python) and ['adapter-package', '1.0'] in item['packages']
               for item in inputs.record()['python_environments'])
    inputs.verify()


def test_debug_inventory_uses_each_child_environment(python_adapter, tmp_path):
    from rvw.common.interpreter import bind_interpreter

    python, _ = python_adapter
    extra = tmp_path / 'extra'
    metadata = extra / 'extra_package-2.0.dist-info'
    metadata.mkdir(parents=True)
    (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: extra-package\nVersion: 2.0\n')
    inputs = DebugInputs()
    environments = {}
    base_env = {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}
    for env in (base_env, {**base_env, 'PYTHONPATH': str(extra)}):
        bind_interpreter(inputs.capture, python, environments=environments, env=env, guard=lambda item: None)
    inventories = list(environments.values())
    assert len(inventories) == 2
    assert ['extra-package', '2.0'] not in inventories[0]['packages']
    assert ['extra-package', '2.0'] in inventories[1]['packages']


@pytest.mark.parametrize('launch', ['shebang', 'interpreter', 'executable'])
def test_debug_unset_path_does_not_use_server_path(python_adapter, monkeypatch, launch):
    python, script = python_adapter
    name = 'rvw-replay-python'
    (python.parent / name).symlink_to(python)
    script.write_text(script.read_text().replace(f'#!{python}', f'#!/usr/bin/env {name}'))
    monkeypatch.setenv('PATH', str(python.parent) + os.pathsep + os.environ['PATH'])
    exe = {'shebang': [str(script)], 'interpreter': [name, str(script)],
           'executable': [name]}[launch]
    with pytest.raises(CaptureError, match='input_not_captured:(interpreter|adapter)'):
        DebugInputs().bind_adapter(Command(exe=exe, unset=['PATH']))


@pytest.mark.parametrize('tool', ['reduce', 'bundle'])
@pytest.mark.parametrize('entry', ['cli', 'mcp'])
@pytest.mark.parametrize('replay_environment', [False, True])
def test_debug_cli_mcp_with_venv_and_sibling(python_adapter, tmp_path, monkeypatch, capsys, tool, entry,
                                          replay_environment):
    import json
    from rvw.cli import main
    from rvw.mcp.registry import Registry
    from test_debug_tools import CFG, SYMS_ELF
    from test_mcp_tools import call

    python, script = python_adapter
    (script.parent / 'support.py').write_text('VALUE = "sibling module"\n')
    fake = Path(__file__).with_name('fake_debug_adapter.py').read_text().split('\n', 1)[1]
    script.write_text(f'#!{python}\nimport adapter_package, support\n'
                      'assert support.VALUE == "sibling module"\n' + fake)
    child_env = dict(os.environ)
    if replay_environment:
        script.write_text(script.read_text().replace(f'#!{python}', '#!/usr/bin/env python'))
        child_env['PATH'] = str(python.parent) + os.pathsep + os.environ['PATH']
        script.write_text(script.read_text().replace('res = {"schema":',
            'replay = "env PATH=" + __import__("shlex").quote(os.environ["PATH"]) + " " + replay\n'
            '    res = {"schema":'))
    config = tmp_path / 'debug.toml'
    config.write_text(CFG)
    monkeypatch.setenv('RVW_CORE_CONFIG', str(config))
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    initial = tmp_path / 'run'
    result = run_group([str(script), 'run', '--elf', SYMS_ELF, '--seed', '9', '--out', str(initial)],
                       env=child_env, capture=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads((initial / 'result.json').read_text())['status'] == 'assert'
    out = tmp_path / 'out'
    if entry == 'cli':
        options = ['--modes', 'cycles'] if tool == 'reduce' else ['--no-spinaltrace']
        assert main([tool, str(initial), '--out', str(out), *options, '--json']) == 0
        report = json.loads(capsys.readouterr().out)
    else:
        registry, problems = Registry.discover({tool})
        assert not problems
        try:
            name = 'reduce_run' if tool == 'reduce' else 'bundle_make'
            options = {'modes': 'cycles'} if tool == 'reduce' else {'no_spinaltrace': True}
            report = call(registry, name, run_dir=str(initial), out=str(out), **options)
        finally:
            registry.jobs.shutdown()
    assert report['reproduced'] if tool == 'reduce' else report['rerun']['reproduced']
