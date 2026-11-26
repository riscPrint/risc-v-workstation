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


def test_common_execution_propagates_env(tmp_path, monkeypatch):
    from rvw.formal import common
    seen = []
    def execute(argv, cwd, log, timeout=None, **kwargs):
        seen.append(kwargs['env'])
        return 124, 0.1
    monkeypatch.setattr(common, 'execute', execute)
    assert common.run(['true'], tmp_path, tmp_path / 'a')[0] == 124
    assert len(seen) == 1 and seen[0] is not None
