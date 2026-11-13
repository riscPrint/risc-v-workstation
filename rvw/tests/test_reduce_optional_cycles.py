"""C1 permits a matching failure without a cycle count."""
from types import SimpleNamespace

import pytest

from rvw.reduce.core import Options, Reducer
from rvw.runs import adapter
from rvw.runs.result import Run
from rvw.results import RunResult

pytestmark = pytest.mark.fast


def test_matching_trial_without_cycles(tmp_path, monkeypatch):
    reducer = Reducer.__new__(Reducer)
    reducer.o = Options()
    reducer.out = tmp_path
    reducer.core = 'fixture'
    reducer.sig = 'fail:1'
    reducer.reference_platform = None
    reducer.trials = []
    command = adapter.Command(env={}, exe=['adapter'], sub='run')
    reducer.best = dict(cycles=100, trial=0, seed=1, mem_latency=None,
                        elf='input.elf', cmd=command)
    result = RunResult(status='fail', fail_code=1)
    run = Run(tmp_path, result, result.to_dict())
    monkeypatch.setattr(adapter, 'execute_many', lambda *a, **kw: [
        SimpleNamespace(run=run, dir=tmp_path, lock_wait=0, error=None)])
    reducer.say = lambda _: None
    reducer.save = lambda: None
    records = reducer.trial([('seed2', command, {'seed': 2})])
    assert records[0]['match'] is True
    assert records[0]['conclusive'] is True
    assert reducer.best['cycles'] == 100
