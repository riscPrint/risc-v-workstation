"""Persistent batches select one worker and skip a redundant build process."""
import pytest
from rvw.regress.config import ConfigError, load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe


def test_persistent_batch_uses_one_worker_and_no_build(fake, tmp_path):
    fake.config.write_text(fake.config.read_text().replace('jobs = 2', 'jobs = 2\npersistent = true'))
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None, jobs=7))
    assert runner.jobs == 1
    assert runner.startup_s == core.startup_s + core.build_timeout_s
    commands = []
    original = runner._proc

    def record(cmd, *args, **kwargs):
        commands.append(cmd)
        # The fixture adapter predates the opt-in. Check the forwarded flag here,
        # then let it produce C1 results with its existing serial implementation.
        if '--persistent' in cmd:
            cmd = [v for v in cmd if v != '--persistent']
        return original(cmd, *args, **kwargs)

    runner._proc = record
    assert runner.run(suites_plan(core, ['isa'], None))['ok']
    batches = [c for c in commands if 'run-many' in c]
    assert batches and all('--persistent' in c and c[c.index('--jobs') + 1] == '1' for c in batches)
    assert not any('build' in c for c in commands)


def test_persistent_requires_boolean(fake):
    fake.config.write_text(fake.config.read_text().replace('jobs = 2', 'jobs = 2\npersistent = "false"'))
    with pytest.raises(ConfigError, match='persistent must be a boolean'):
        load_config(str(fake.config))
