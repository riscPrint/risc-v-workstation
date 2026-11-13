"""Related persistent workers inherit locks; unrelated threads still do not."""
from concurrent.futures import ThreadPoolExecutor
import sys
import pytest
from rvw.common import lock
from rvw.common.proc import run_group
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe

pytestmark = pytest.mark.fast


def test_forwarded_lock_can_be_reentered_by_worker_child(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_LOCK_DIR', str(tmp_path/'locks'))
    with lock.held('worker-test', log=None):
        forward = lock.thread_context()
        def worker():
            with forward():
                return run_group([sys.executable, '-m', 'rvw.common.lock', 'worker-test',
                                  sys.executable, '-c', 'print("entered")'], capture=True, timeout=3)
        with ThreadPoolExecutor(1) as pool:
            result = pool.submit(worker).result(timeout=10)
        assert result.returncode == 0 and not result.timed_out
        assert result.stdout.strip() == 'entered'
    with lock.held('worker-test', log=None):
        with pytest.raises(ValueError, match='expired'):
            with forward():
                pass


def test_runner_forwards_core_lock_to_persistent_worker(fake, tmp_path):
    fake.config.write_text(fake.config.read_text().replace('jobs = 2', 'jobs = 2\npersistent = true'))
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path/'out', RunOptions(index=False, log=None, jobs=2))
    original = runner._proc
    inherited = []
    def run(cmd, *args, **kwargs):
        if 'run-many' in cmd:
            inherited.append(lock.held_fds())
            cmd = [v for v in cmd if v != '--persistent']
        return original(cmd, *args, **kwargs)
    runner._proc = run
    try:
        assert runner.run(suites_plan(core, ['isa'], None))['ok']
    finally:
        runner.close()
    assert len(inherited) == 2 and all(inherited)
