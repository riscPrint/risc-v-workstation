"""Persistent batches isolate workers and skip a redundant build process."""
import pytest
from rvw.regress.config import ConfigError, load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe


def test_persistent_batch_uses_isolated_workers_and_no_build(fake, tmp_path):
    fake.config.write_text(fake.config.read_text().replace('jobs = 2', 'jobs = 2\npersistent = true'))
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None, jobs=7))
    assert runner.jobs == 7
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


def test_native_profile_defaults_to_persistent(fake):
    fake.config.write_text(fake.config.read_text().replace('name = "fake"',
        'name = "fake"\nbackend = "riscvsim-verilator"'))
    assert load_config(str(fake.config)).persistent
    fake.config.write_text(fake.config.read_text().replace('jobs = 2',
        'jobs = 2\npersistent = false'))
    assert not load_config(str(fake.config)).persistent


def test_worker_shards_run_in_parallel_and_preserve_order():
    import threading
    from rvw.sim.persistent import run_workers
    ready = threading.Barrier(3, timeout=5)

    def run(number, batch, cancel):
        ready.wait()
        return number, batch

    assert run_workers(list(range(8)), 3, run) == [
        (0, [0, 3, 6]), (1, [1, 4, 7]), (2, [2, 5])]
    assert run_workers([], 8, run) == []
    with pytest.raises(ValueError):
        run_workers([1], 0, run)


def test_crashed_worker_does_not_discard_other_results():
    from rvw.sim.persistent import run_workers
    def run(number, batch, cancel):
        return (2, False) if number == 0 else (0, False)
    assert run_workers([1, 2], 2, run) == [(2, False), (0, False)]


def test_worker_pool_cancels_other_workers_before_return():
    import threading
    from rvw.sim.persistent import run_workers
    ready = threading.Barrier(2, timeout=5)
    stopped = threading.Event()

    def run(number, batch, cancel):
        ready.wait()
        if number == 1:
            raise RuntimeError("injected worker failure")
        assert cancel.wait(5)
        stopped.set()

    with pytest.raises(RuntimeError, match="injected"):
        run_workers([1, 2], 2, run)
    assert stopped.is_set()


def test_persistent_crash_retries_missing_jobs_in_fresh_processes(fake, tmp_path):
    fake.config.write_text(fake.config.read_text().replace('jobs = 2',
        'jobs = 2\npersistent = true'))
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out',
                    RunOptions(index=False, log=None, jobs=2))
    original = runner._proc
    batches = []

    def crash_first(cmd, log, timeout, **kwargs):
        if 'run-many' in cmd:
            batches.append(cmd)
            manifest = cmd[cmd.index('--manifest') + 1]
            if 'worker-0' in manifest:
                return 3, False, 0.01
            cmd = [arg for arg in cmd if arg != '--persistent']
        return original(cmd, log, timeout, **kwargs)

    runner._proc = crash_first
    result = runner.run(suites_plan(core, ['isa'], None))
    assert result['ok']
    assert any('manifest-retry.jsonl' in ' '.join(cmd) for cmd in batches)
    assert all(cmd[cmd.index('--jobs') + 1] == '1' for cmd in batches)


def test_pool_exception_stops_running_process_group(fake, tmp_path):
    import os
    import sys
    import threading
    fake.config.write_text(fake.config.read_text().replace('jobs = 2',
        'jobs = 2\npersistent = true'))
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out',
                    RunOptions(index=False, log=None, jobs=2))
    original = runner._proc
    started = threading.Event()
    pidfile = tmp_path / 'child.pid'

    def inject(cmd, log, timeout, **kwargs):
        if 'run-many' not in cmd:
            return original(cmd, log, timeout, **kwargs)
        manifest = cmd[cmd.index('--manifest') + 1]
        if 'worker-1' in manifest:
            assert started.wait(10)
            raise RuntimeError('injected pool failure')
        watchdog = kwargs['watchdog']
        def watch():
            started.set()
            return watchdog()
        code = ('import os, pathlib, time; '
                f'pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid())); '
                'time.sleep(60)')
        return original([sys.executable, '-c', code], log, 15, watchdog=watch)

    runner._proc = inject
    with pytest.raises(RuntimeError, match='injected pool failure'):
        runner.run(suites_plan(core, ['isa'], None))
    assert pidfile.exists()
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)
