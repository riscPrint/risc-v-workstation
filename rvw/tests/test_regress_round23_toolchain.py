"""Only the native build's selected compiler commands are required."""
from pathlib import Path
import shutil
import sys

import pytest

from rvw.regress.captured import Inputs
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe


def executable(path, body):
    path.write_text(f'#!{sys.executable}\n' + body)
    path.chmod(0o755)


def toolchain(fake, tmp_path, monkeypatch, *, compiler='g++', linker='g++', environment=None):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    install = tmp_path / 'verilator'
    (install / 'include').mkdir(parents=True)
    (install / 'include/verilated.mk').write_text(f'CXX = {compiler}\nLINK = {linker}\n')
    executable(bindir / 'verilator',
               f'import sys\nprint({str("VERILATOR_ROOT = " + str(install))!r} '
               'if "-V" in sys.argv else "Verilator fixture 1")\n')
    for name in ['g++', 'gcc', 'selected-cxx', 'selected-cc']:
        executable(bindir / name, f'print({name!r} + " fixture 1")\n')
    (bindir / 'git').symlink_to(shutil.which('git'))
    monkeypatch.setenv('PATH', str(bindir))
    for key in ['CXX', 'CC']:
        monkeypatch.delenv(key, raising=False)
    for key, value in (environment or {}).items():
        monkeypatch.setenv(key, value)
    core = load_config(str(fake.config))
    shipped = load_config('boom')
    # Keep compiler requirements from the shipped config, with fixture build infrastructure.
    alternatives = {'g++', 'gcc', 'c++', 'cc', 'clang', 'clang++'}
    core.input_tools = ['verilator', *(name for name in shipped.input_tools if name in alternatives)]
    core.input_verilator_toolchain = getattr(shipped, 'input_verilator_toolchain', False)
    core.input_env += ['CXX', 'CC']
    return core, bindir, install


def test_boom_runs_without_unused_clang_commands(fake, tmp_path, monkeypatch):
    core, _, install = toolchain(fake, tmp_path, monkeypatch)
    with Runner(core, describe(fake.repo), tmp_path / 'out',
                RunOptions(index=False, use_cache=False, log=None)) as runner:
        assert runner.inputs.problem is None
        records = runner.inputs.record()
        tools = {Path(record['source']).name for record in records['tools']}
        assert 'g++' in tools
        assert not tools & {'clang', 'clang++', 'gcc', 'cc', 'c++'}
        assert any(Path(record['source']) == install / 'include/verilated.mk'
                   for record in records['files'])
        assert runner.run(suites_plan(core, ['isa'], None))['ok']


def test_selected_linker_and_environment_compilers_are_captured(fake, tmp_path, monkeypatch):
    core, _, _ = toolchain(fake, tmp_path, monkeypatch, linker='gcc',
                          environment={'CXX': 'selected-cxx', 'CC': 'selected-cc'})
    inputs = Inputs(core, describe(fake.repo))
    try:
        assert inputs.problem is None
        tools = {Path(record['source']).name for record in inputs.record()['tools']}
        assert tools >= {'g++', 'gcc', 'selected-cxx', 'selected-cc'}
        assert inputs.child_env['PATH'] == str(tmp_path / 'bin')
    finally:
        inputs.close()


@pytest.mark.parametrize('compiler,linker', [('clang++', 'g++'), ('g++', 'clang++'),
                                           ('$(CXX)', 'g++'), ('ccache g++', 'g++')])
def test_missing_or_opaque_selected_tools_refuse_execution(fake, tmp_path, monkeypatch, compiler, linker):
    core, _, _ = toolchain(fake, tmp_path, monkeypatch, compiler=compiler, linker=linker)
    with Runner(core, describe(fake.repo), tmp_path / 'out',
                RunOptions(index=False, use_cache=False, log=None)) as runner:
        summary = runner.run(suites_plan(core, ['isa'], None))
        assert not summary['ok'] and summary['inconclusive'] == 3
        assert 'input_not_captured:' in runner.inputs.problem
        assert not fake.calls('run') and not fake.calls('build')


def test_missing_environment_compiler_refuses_execution(fake, tmp_path, monkeypatch):
    core, _, _ = toolchain(fake, tmp_path, monkeypatch, environment={'CC': 'missing-cc'})
    inputs = Inputs(core, describe(fake.repo))
    try:
        assert 'input_not_captured:tool:missing-cc' in inputs.problem
    finally:
        inputs.close()


def test_toolchain_config_requires_boolean(fake):
    from rvw.regress.config import ConfigError
    fake.config.write_text(fake.config.read_text().replace(
        'input_complete = true', 'input_complete = true\ninput_verilator_toolchain = "true"'))
    with pytest.raises(ConfigError, match='input_verilator_toolchain'):
        load_config(str(fake.config))
