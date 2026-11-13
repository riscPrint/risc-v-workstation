"""A shared build failure must not trigger one cold build per workload."""
from types import SimpleNamespace
import pytest
from rvw.runs import adapter
pytestmark = pytest.mark.fast


@pytest.mark.parametrize('fallback,expected', [(False,1), (True,3)])
def test_batch_build_failure(tmp_path, monkeypatch, fallback, expected):
    calls = []
    def run(*args, **kw):
        calls.append(args)
        return SimpleNamespace(returncode=2, timed_out=False)
    monkeypatch.setattr(adapter, 'run_group', run)
    commands = [adapter.Command(exe=['missing-adapter']).set(elf='missing.elf') for _ in range(2)]
    attempts = adapter.execute_many(commands, [tmp_path/'a', tmp_path/'b'], fallback=fallback)
    assert len(attempts) == 2
    assert all(a.run is None for a in attempts)
    assert len(calls) == expected
