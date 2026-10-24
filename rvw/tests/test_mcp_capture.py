"""MCP transport keeps worker isolation and rejects failed result channels."""
import json
import sys
from pathlib import Path

import pytest

from rvw.common.proc import run_group
from rvw.mcp.spec import ToolError
from rvw.mcp.worker import run_function


class Job:
    def set_progress(self, message):
        pass

    def check(self):
        pass

    def run(self, command):
        self.command = command
        return run_group(command, capture=True, timeout=30).returncode


@pytest.mark.parametrize('lock', [None, 'debug-worker-test'])
def test_worker_uses_installed_python_and_private_channel(tmp_path, monkeypatch, lock):
    monkeypatch.setenv('RVW_LOCK_DIR', str(tmp_path / 'locks'))
    job = Job()
    assert run_function(job, 'json', 'dumps', {'obj': 1}, lock) == '1'
    assert job.command[:3] == [sys.executable, '-m',
                             'rvw.common.lock' if lock else 'rvw.mcp.worker']
    assert not Path(job.command[-2]).exists()  # private transport was removed


@pytest.mark.parametrize('envelope,rc,match', [
    (None, 2, 'without a result'),
    ({'error': 'worker failure'}, 0, 'worker failure'),
    ({'result': 'stale success'}, 2, 'worker exited 2'),
])
def test_failed_worker_never_returns_success(envelope, rc, match):
    class FailedJob(Job):
        def run(self, command):
            if envelope is not None:
                Path(command[-1]).write_text(json.dumps(envelope))
            return rc

    with pytest.raises(ToolError, match=match):
        run_function(FailedJob(), 'json', 'dumps', {'obj': 1})


@pytest.mark.parametrize('action', ['prove', 'mutate'])
@pytest.mark.parametrize('environment,override,expected', [
    (None, None, 'boom'), ('coverage', None, 'coverage'), ('', None, None),
    ('coverage', 'selected', 'selected'), ('coverage', '', None),
])
def test_coverage_worker_keeps_dynamic_lock(monkeypatch, action, environment, override, expected):
    from rvw.cov.mcp_tools import _locked

    if environment is None:
        monkeypatch.delenv('RVW_HEAVY_LOCK', raising=False)
    else:
        monkeypatch.setenv('RVW_HEAVY_LOCK', environment)
    calls = []
    def run(job, module, function, arguments, lock):
        calls.append((module, function, arguments, lock))
        return {'result': 'fixture'}
    monkeypatch.setattr('rvw.mcp.worker.run_function', run)
    assert _locked(action)(Job(), lock=override, project='fixture') == {'result': 'fixture'}
    assert calls == [('rvw.cov.cli', 'execute_json', {'action': action, 'project': 'fixture'}, expected)]
