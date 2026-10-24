"""Normal output paths, virtual environments and platform command declarations."""
from pathlib import Path
import sys
import venv

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe


@pytest.mark.parametrize('shebang', [False, True])
@pytest.mark.parametrize('declare_tree', [False, True])
def test_adapter_keeps_virtual_environment(fake, tmp_path, shebang, declare_tree):
    environment = tmp_path / 'adapter-env'
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    python = environment / 'bin/python'
    packages = environment / f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'
    (packages / 'rvw_venv_only.py').write_text('MARKER = "venv package"\n')
    metadata = packages / 'rvw_venv_only-1.0.dist-info'
    metadata.mkdir()
    (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: rvw-venv-only\nVersion: 1.0\n')
    adapter = tmp_path / 'adapter.py'
    original = Path(__file__).with_name('fake_adapter.py').read_text()
    header = f'#!{python}\n' if shebang else ''
    adapter.write_text(header + 'import rvw_venv_only\nassert rvw_venv_only.MARKER == "venv package"\n' + original)
    adapter.chmod(0o755)
    core = load_config(str(fake.config))
    core.adapter = [str(adapter)] if shebang else [str(python), str(adapter)]
    core.cache_paths = [environment] if declare_tree else []
    runner = Runner(core, describe(fake.repo), tmp_path / 'output', RunOptions(index=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert summary['ok'], (summary, runner.adapter)
    assert runner.adapter[0] == str(python)
    inventory = runner.adapter_id['python_environments']
    assert any(['rvw-venv-only', '1.0'] in item['packages'] for item in inventory)
    before = runner.tools_key
    (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: rvw-venv-only\nVersion: 2.0\n')
    changed = Runner(core, describe(fake.repo), tmp_path / 'changed', RunOptions(index=False, log=None))
    assert changed.tools_key != before


@pytest.mark.parametrize('failure', ['exit', 'timeout', 'invalid'])
def test_unknown_python_packages_refuse_results_and_cache(fake, tmp_path, monkeypatch, failure):
    from rvw.common.proc import Result
    from rvw.regress import captured
    original = captured.run_group

    def inventory(argv, **kwargs):
        if any('import importlib.metadata' in arg for arg in argv):
            return Result(1 if failure == 'exit' else 0, timed_out=failure == 'timeout',
                          stdout='invalid' if failure == 'invalid' else '[]')
        return original(argv, **kwargs)

    monkeypatch.setattr(captured, 'run_group', inventory)
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'output', RunOptions(index=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert not summary['ok'] and summary['inconclusive'] == 3
    assert 'input_not_captured:python_environment' in runner.input_change
    assert runner.tools_key is None and not fake.calls('run')
