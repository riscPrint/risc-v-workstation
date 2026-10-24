"""Round 22: stable build identities and bounded capture lifetime."""
import importlib.util
import json
from pathlib import Path

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan, gate
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe


def helper(name):
    path = Path(__file__).resolve().parents[2] / 'RiscvSim/scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finished_runs_remove_private_inputs(fake, tmp_path):
    core = load_config(str(fake.config))
    for index in range(3):
        runner = Runner(core, describe(fake.repo), tmp_path / f'out-{index}',
                        RunOptions(index=False, log=None, results_root=tmp_path / 'results'))
        assert runner.run(suites_plan(core, ['isa'], None))['ok']
        assert not runner.inputs.directory.exists()


def test_constructor_failure_removes_private_inputs(fake, tmp_path, monkeypatch):
    import rvw.regress.captured as captured
    paths = []
    original = captured.private_directory
    def allocate(*args, **kwargs):
        path = original(*args, **kwargs)
        paths.append(path)
        return path
    monkeypatch.setattr(captured, 'private_directory', allocate)
    def fail(*args, **kwargs):
        raise OSError('injected initialization error')
    monkeypatch.setattr(captured.Inputs, '_initialize', fail)
    core = load_config(str(fake.config))
    with pytest.raises(OSError, match='injected'):
        Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False))
    assert paths and not any(path.exists() for path in paths)


def test_native_identity_ignores_runner_routing_but_binds_options(tmp_path, monkeypatch):
    module = helper('native-identity.py')
    before = module.collect()
    # Runner metadata no longer routes native tools or sources.
    monkeypatch.setenv('RVW_CAPTURE_INPUTS', str(tmp_path / 'unused-routing.json'))
    monkeypatch.setenv('RVW_CAPTURE_SOURCE', '{"core_rev":"different"}')
    after = module.collect()
    assert before['sha256'] == after['sha256']
    assert before['environment_sha256'] == after['environment_sha256']
    monkeypatch.setenv('SPINAL_VERILATOR_FLAGS', '-CFLAGS -DNEW_OPTION=1')
    assert module.collect()['sha256'] != before['sha256']


def test_failed_run_and_preview_remove_private_inputs(fake, tmp_path, monkeypatch):
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False))
    def fail(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(runner, '_run', fail)
    with pytest.raises(KeyboardInterrupt):
        runner.run(suites_plan(core, ['isa'], None))
    assert not runner.inputs.directory.exists()
    preview = Runner(core, describe(fake.repo), tmp_path / 'preview', RunOptions(index=False))
    preview.preview(suites_plan(core, ['isa'], None))
    assert not preview.inputs.directory.exists()


@pytest.mark.parametrize('failure', [False, True])
def test_gate_cleans_shared_capture_and_prepared_sides(fake, tmp_path, monkeypatch, failure):
    import rvw.regress.captured as captured
    import rvw.regress.plan as planning
    paths = []
    original = captured.private_directory
    def allocate(*args, **kwargs):
        path = original(*args, **kwargs)
        paths.append(path)
        return path
    monkeypatch.setattr(captured, 'private_directory', allocate)
    if failure:
        def fail(*args):
            raise KeyboardInterrupt()
        monkeypatch.setattr(planning.Runner, 'capture_plan', fail)
    core = load_config(str(fake.config))
    revision = describe(fake.repo).rev
    def run():
        return gate(core, 'quick', revision, revision, None, None, None,
                    RunOptions(results_root=tmp_path / 'store', index=False, log=None), None, None)
    if failure:
        with pytest.raises(KeyboardInterrupt):
            run()
    else:
        assert run()['verdict'].verdict == 'accept'
    assert paths and not any(path.exists() for path in paths)


def test_saved_replay_elf_survives_cleanup_and_has_a_size_bound(fake, tmp_path):
    import shlex
    from rvw.results import find_results, load_run
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False))
    assert runner.run(suites_plan(core, ['isa'], None))['ok']
    for suite in find_results(runner.out):
        for test in suite.tests:
            result = load_run(suite.path / test.run)
            elf = Path(shlex.split(result.replay)[3])
            assert elf.is_file() and elf.read_bytes() == (fake.isa / test.id).read_bytes()
            assert str(runner.inputs.directory) not in result.replay
            assert '/generations/' in str(elf)
            argv = shlex.split(result.replay)
            assert '/generations/' not in argv[argv.index('--out') + 1]
    runner = Runner(core, describe(fake.repo), tmp_path / 'limited',
                    RunOptions(index=False, use_cache=False))
    runner.inputs.capture.max_tree_bytes = 1
    with pytest.raises(Exception, match='replay_size'):
        runner.run(suites_plan(core, ['isa'], None))
    assert not runner.inputs.directory.exists()
    assert not (runner.out / 'current').exists()


@pytest.mark.parametrize('signum', [2, 15])
def test_cli_cancellation_stops_adapter_before_removing_inputs(fake, tmp_path, signum):
    import os
    import signal
    import subprocess
    import sys
    import time
    from rvw.common.proc import kill_group
    core = load_config(str(fake.config))
    fake.prog('rv64ui-p-add', 'sleep=120')
    owned = tmp_path / 'owned-inputs'
    owned.mkdir()
    script = tmp_path / 'cancel.py'
    script.write_text('''import pathlib, tempfile
from rvw.cli import main
from rvw.regress import captured
captured.tempfile.gettempdir = lambda: ROOT
raise SystemExit(main(['regress', 'run', '--core', CONFIG, '--suite', 'isa',
                      '--filter', '^rv64ui-p-add$', '--out', OUT, '--json']))
'''.replace('ROOT', repr(str(owned))).replace('CONFIG', repr(str(fake.config)))
                   .replace('OUT', repr(str(tmp_path / 'cancel-out'))))
    with (tmp_path / 'cancel.log').open('w') as log:
        process = subprocess.Popen([sys.executable, str(script)], env=os.environ.copy(),
                                   stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 20
            while not fake.calls('run'):
                assert time.monotonic() < deadline and process.poll() is None
                time.sleep(0.1)
            assert list(owned.glob('.rvw-inputs-*'))
            os.kill(process.pid, signum)
            process.wait(timeout=15)
        finally:
            kill_group(process, grace=0.2)
    assert process.returncode != 0
    assert not list(owned.glob('.rvw-inputs-*'))
    # No late adapter write can occur after cleanup.
    assert not list((tmp_path / 'cancel-out').rglob('result.json'))


def test_abandoned_runner_releases_its_capture(fake, tmp_path):
    import gc
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False))
    directory = runner.inputs.directory
    del runner
    gc.collect()
    assert not directory.exists()


def test_declared_command_identity_is_stable_between_runs(fake, tmp_path):
    from rvw.results import find_results
    core = load_config(str(fake.config))
    core.input_commands = ['cat']
    core.identity = True
    options = RunOptions(results_root=tmp_path / 'store', index=False, log=None)
    plan = suites_plan(core, ['isa'], None)
    first = Runner(core, describe(fake.repo), tmp_path / 'first', options)
    assert first.run(plan)['ok']
    calls = len(fake.calls('run'))
    second = Runner(core, describe(fake.repo), tmp_path / 'cached', options)
    assert second.run(plan)['ok'] and len(fake.calls('run')) == calls
    assert second.identities == first.identities
    assert all(t.extra.get('cached') for suite in find_results(second.out) for t in suite.tests)
