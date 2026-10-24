"""Replay storage counts unique captured inputs before any build or simulation."""
import hashlib
from dataclasses import replace
from pathlib import Path
import shlex

import pytest

from rvw.common.capture import CaptureError
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results, load_run
from rvw.results.generation import open_current


def make_runner(fake, tmp_path, *, out='out', cache=False, alias=False):
    core = load_config(str(fake.config))
    if alias:
        core.suites['alias'] = replace(core.suite('isa'), name='alias')
    runner = Runner(core, describe(fake.repo), tmp_path / out,
                    RunOptions(seeds=4, index=False, log=None, use_cache=cache))
    return runner, suites_plan(core, ['isa', 'alias'] if alias else ['isa'], ['small', 'large'])


def replay_inputs(out, fake):
    paths = []
    for suite in find_results(out):
        for test in suite.tests:
            result = load_run(suite.path / test.run)
            argv = shlex.split(result.replay)
            elf = Path(argv[argv.index('--elf') + 1])
            assert elf.read_bytes() == (fake.isa / test.id).read_bytes()
            assert result.artifact('replay_elf').resolve() == elf.resolve()
            assert '/generations/' in str(elf)
            assert '/generations/' not in argv[argv.index('--out') + 1]
            paths.append(elf)
    return paths


def test_replay_storage_deduplicates_content_across_seeds_suites_and_configs(fake, tmp_path):
    fake.prog('rv64ui-p-sub')  # Three different paths now have identical bytes.
    runner, plan = make_runner(fake, tmp_path, alias=True)
    runner.inputs.capture.max_tree_bytes = len(b'status=pass\n')
    assert runner.run(plan)['ok']
    paths = replay_inputs(runner.out, fake)
    assert len(paths) == 48
    assert len(set(paths)) == 1
    generation = open_current(runner.out)
    assert sum(p.stat().st_size for p in generation.path.rglob('*.elf')) == len(b'status=pass\n')


def test_replay_budget_refuses_before_build_or_simulation(fake, tmp_path):
    runner, plan = make_runner(fake, tmp_path)
    runner.inputs.capture.max_tree_bytes = 1
    with pytest.raises(CaptureError, match=r'replay_size.*--replay-max-bytes'):
        runner.run(plan)
    assert not fake.calls('build') and not fake.calls('run')
    assert not (runner.out / 'current').exists()
    assert not runner.inputs.directory.exists()


def test_replay_inputs_survive_resume_and_cache_restore(fake, tmp_path):
    runner, plan = make_runner(fake, tmp_path, cache=True)
    assert runner.run(plan)['ok']
    original = open_current(runner.out)
    first_paths = replay_inputs(runner.out, fake)
    fake.reset_calls()
    resumed, plan = make_runner(fake, tmp_path, cache=True)
    assert resumed.run(plan)['ok']
    assert not fake.calls('run')
    replay_inputs(resumed.out, fake)
    cached, plan = make_runner(fake, tmp_path, out='cached', cache=True)
    assert cached.run(plan)['ok']
    assert not fake.calls('run')
    replay_inputs(cached.out, fake)
    for path in first_paths:
        relative = path.relative_to(original.path)
        assert hashlib.sha256(original.read_bytes(relative)).hexdigest() == path.stem


def test_cli_can_raise_replay_budget(fake, tmp_path, rvw):
    args = ['regress', 'run', '--core', fake.config, '--suite', 'isa', '--no-cache', '--no-index']
    code, _, _ = rvw(*args, '--out', tmp_path / 'small', '--replay-max-bytes', '1', '--json')
    assert code != 0 and not fake.calls('run')
    code, _, data = rvw(*args, '--out', tmp_path / 'raised', '--replay-max-bytes', '1024', '--json')
    assert code == 0 and data['ok']


def test_structured_api_can_raise_replay_budget(fake, tmp_path):
    from rvw.regress.cli import execute_json
    result = execute_json('run', core=str(fake.config), suite='isa', out=str(tmp_path / 'api'),
                          replay_max_bytes=1024, no_cache=True, no_index=True)
    assert result['ok']


@pytest.mark.parametrize('limit', [0, -1, True, 1.5])
def test_invalid_replay_budget_is_refused(limit):
    from rvw.regress.config import ConfigError
    with pytest.raises(ConfigError, match='replay_max_bytes'):
        RunOptions(replay_max_bytes=limit)
