"""Review 18: recorded ELF bytes must survive rebuilds during debug work."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from rvw.bisect.core import Bisector, Options as XOpts
from rvw.bundle.make import make, Options as BOpts
from rvw.reduce.core import Reducer, Options as ROpts
from rvw.runs import adapter
from rvw.runs.elf import Elf
from test_debug_tools import CFG, SYMS_ELF, fake_run_elf, make_core, _spinaltrace_cfg


@pytest.fixture(autouse=True)
def debug_env(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    monkeypatch.setenv('FAKE_SYMBOL', 'limit>=7')
    cfg = tmp_path / 'debug.toml'
    cfg.write_text(CFG)
    monkeypatch.setenv('RVW_CORE_CONFIG', str(cfg))


def recorded(tmp_path):
    elf = tmp_path / 'program.elf'
    elf.write_bytes(Path(SYMS_ELF).read_bytes())
    return fake_run_elf(tmp_path / 'run', str(elf), '--seed', '9'), elf


def rebuild(elf):
    e = Elf(str(elf))
    e.write_int('limit', 3)
    e.save(str(elf))


@pytest.mark.parametrize('tool', ['reduce', 'bisect', 'bundle'])
@pytest.mark.parametrize('identity', ['changed', 'missing', 'invalid', 'missing-file'])
def test_debug_refuses_unverified_elf(tmp_path, tool, identity):
    run, elf = recorded(tmp_path)
    if identity == 'changed':
        rebuild(elf)
    elif identity == 'missing-file':
        elf.unlink()
    else:
        p = run / 'result.json'
        data = json.loads(p.read_text())
        data['elf_sha256'] = None if identity == 'missing' else '0'
        p.write_text(json.dumps(data))
    repo, _ = make_core(tmp_path)
    with pytest.raises((ValueError, OSError), match='ELF|elf_sha256|program.elf'):
        if tool == 'reduce':
            Reducer(str(run), ROpts(out=tmp_path / 'reduce', modes=['symbols'], symbols=['limit'], exhaustive=True)).reduce()
        elif tool == 'bisect':
            Bisector(str(run), XOpts(good='HEAD~7', core_repo=str(repo), workdir=tmp_path / 'bisect')).bisect()
        else:
            make(str(run), BOpts(out=tmp_path / 'bundle', spinaltrace=False))
    assert not list(tmp_path.glob('**/rerun.log'))
    assert not (tmp_path / 'bisect' / 'core').exists()


def test_reduce_rebuild_between_trials_keeps_replay(tmp_path, monkeypatch):
    run, elf = recorded(tmp_path)
    expected = hashlib.sha256(elf.read_bytes()).hexdigest()
    execute_many = adapter.execute_many
    commands = []

    def trials(cmds, *args, **kw):
        if commands:
            rebuild(elf)
        commands.extend(cmds)
        return execute_many(cmds, *args, **kw)

    monkeypatch.setattr(adapter, 'execute_many', trials)
    report = Reducer(str(run), ROpts(out=tmp_path / 'reduce', modes=['cycles', 'latency'], latencies=[5])).reduce()
    assert len(commands) >= 2 and report['reproduced']
    for cmd in commands:
        assert Path(cmd.get('elf')) != elf
        assert hashlib.sha256(Path(cmd.get('elf')).read_bytes()).hexdigest() == expected
    replay = adapter.parse_replay(report['best']['replay'])
    attempt = adapter.execute(replay, tmp_path / 'replay')
    assert attempt.run.get('status') == 'assert'


def test_reduce_symbols_bind_to_saved_bytes(tmp_path):
    run, elf = recorded(tmp_path)
    reducer = Reducer(str(run), ROpts(out=tmp_path / 'reduce', modes=['symbols'], symbols=['limit'], exhaustive=True))
    rebuild(elf)
    report = reducer.reduce()
    symbol = report['symbols']['limit']
    assert symbol['original'] == 100
    assert symbol['smallest_failing'] == 7 and symbol['exact']
    assert Elf(symbol['elf']).read_int('limit') == 7
    assert adapter.execute(adapter.parse_replay(report['best']['replay']), tmp_path / 'replay').run.get('status') == 'assert'


def test_bisect_rebuild_between_revisions_uses_one_elf(tmp_path, monkeypatch):
    run, elf = recorded(tmp_path)
    repo, git = make_core(tmp_path)
    execute = adapter.execute
    commands = []

    def trial(cmd, *args, **kw):
        if commands:
            rebuild(elf)
        commands.append(cmd)
        return execute(cmd, *args, **kw)

    monkeypatch.setattr(adapter, 'execute', trial)
    report = Bisector(str(run), XOpts(good='HEAD~7', core_repo=str(repo), workdir=tmp_path / 'bisect')).bisect()
    assert report['result']['first_bad'] == git('rev-parse', 'HEAD~3')
    assert len(commands) >= 3
    assert all(Path(c.get('elf')) != elf and Elf(c.get('elf')).read_int('limit') == 100 for c in commands)
    assert adapter.parse_replay(report['command']).get('elf') == commands[0].get('elf')


@pytest.mark.parametrize('instrumented', [False, True])
def test_bundle_rebuild_keeps_rerun_and_replay(tmp_path, monkeypatch, instrumented):
    run, elf = recorded(tmp_path)
    if instrumented:
        _spinaltrace_cfg(tmp_path, monkeypatch)
    execute = adapter.execute
    commands = []

    def trial(cmd, *args, **kw):
        rebuild(elf)
        commands.append(cmd)
        return execute(cmd, *args, **kw)

    monkeypatch.setattr(adapter, 'execute', trial)
    out = tmp_path / 'bundle'
    report = make(str(run), BOpts(out=out, spinaltrace=instrumented, rerun_window=30, cut_cycles=10))
    assert report['rerun']['reproduced']
    if instrumented:
        assert report['rerun_spinaltrace']['reproduced']
    assert all(Path(c.get('elf')) != elf and Elf(c.get('elf')).read_int('limit') == 100 for c in commands)
    subprocess.run(['bash', str(out / 'replay.sh'), str(tmp_path / 'replay')], check=True, env=os.environ)
    assert json.loads((tmp_path / 'replay' / 'result.json').read_text())['status'] == 'assert'


@pytest.mark.parametrize('tamper', ['bytes', 'symlink'])
def test_saved_elf_is_never_overwritten(tmp_path, tamper):
    from rvw.runs import open_run
    from rvw.runs.inputs import snapshot_elf
    run, elf = recorded(tmp_path)
    out = tmp_path / 'saved'
    saved = snapshot_elf(open_run(run), out)
    if tamper == 'symlink':
        saved.unlink()
        saved.symlink_to(elf)
    else:
        saved.chmod(0o644)
        saved.write_bytes(b'changed saved bytes')
    before = saved.read_bytes()
    with pytest.raises(ValueError, match='saved ELF'):
        snapshot_elf(open_run(run), out)
    assert saved.read_bytes() == before
    assert not list(out.glob('.elf-*'))


def test_snapshot_reuse_keeps_old_replays(tmp_path):
    from rvw.runs import open_run
    from rvw.runs.inputs import snapshot_elf
    run, elf = recorded(tmp_path)
    out = tmp_path / 'saved'
    original = snapshot_elf(open_run(run), out)
    assert original == snapshot_elf(open_run(run), out)
    assert not original.stat().st_mode & 0o222
    rebuild(elf)
    new_run = fake_run_elf(tmp_path / 'new-run', str(elf), '--seed', '9')
    new = snapshot_elf(open_run(new_run), out)
    assert original != new
    assert Elf(str(original)).read_int('limit') == 100
    assert Elf(str(new)).read_int('limit') == 3
    assert not list(out.glob('.elf-*'))
