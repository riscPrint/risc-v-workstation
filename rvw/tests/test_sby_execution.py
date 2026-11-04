from rvw.common import sby
from rvw.common.proc import Result


def test_timeout_overrides_process_code(tmp_path, monkeypatch):
    seen = {}
    def run(argv, **kwargs):
        seen.update(kwargs)
        return Result(0, timed_out=True)
    monkeypatch.setattr(sby, 'run_group', run)
    env = {'PATH': '/captured'}
    rc, seconds = sby.execute(['/captured/sby'], tmp_path, tmp_path / 'log', 2, env=env)
    assert rc == 124 and seconds >= 0
    assert seen['env'] is env and seen['timeout'] == 2 and seen['grace'] == 10


def test_both_callers_use_shared_execution(tmp_path, monkeypatch):
    from rvw.formal import common
    from rvw.cov import proof
    seen = []
    def execute(argv, cwd, log, timeout=None, **kwargs):
        seen.append(kwargs['env'])
        return 124, 0.1
    monkeypatch.setattr(common, 'execute', execute)
    monkeypatch.setattr(proof, 'execute', execute)
    assert common.run(['true'], tmp_path, tmp_path / 'a')[0] == 124
    assert proof.run_job(['true'], tmp_path, tmp_path / 'b', 1) == 124
    assert len(seen) == 2 and seen[1] is not None
