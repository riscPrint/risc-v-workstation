import base64
import json
import os
from pathlib import Path
import sys

import pytest

from rvw.common.budget import Budget, supervise
from rvw.regress.store import Cache
from rvw.results.generation import open_current


def test_cache_key_and_artifact_integrity(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "result.json").write_text('{"status":"pass"}')
    cache = Cache(tmp_path / "cache")
    key = "a" * 64
    cache.put(key, source)
    assert cache.get("b" * 64) is None
    reader = open_current(cache.path(key))
    assert reader.read_bytes(".rvw-cache-key").decode() == key
    reader.path.chmod(0o700)
    (reader.path / "result.json").unlink()
    with pytest.raises(ValueError):
        Cache(tmp_path / "cache").get(key)

@pytest.mark.parametrize("damage", ["evicted", "partial", "wrong-key"])
def test_remote_cache_round_trip_and_eviction(tmp_path, monkeypatch, damage):
    options = os.environ.get("RVW_TEST_SSH_OPTIONS")
    if not options:
        pytest.skip("native localhost SSH required")
    monkeypatch.setenv("RVW_CACHE_SSH_OPTIONS", options)
    remote = tmp_path / "remote"
    monkeypatch.setenv("RVW_REMOTE_CACHE", "localhost:" + str(remote))
    source = tmp_path / "source"
    source.mkdir()
    (source / "result.json").write_text('{"status":"pass"}')
    key = "c" * 64
    first = Cache(tmp_path / "first")
    first.put(key, source)
    assert (remote / key[:2] / key / "current").is_file()
    second = Cache(tmp_path / "second")
    assert second.get(key) is not None
    assert second.get("d" * 64) is None
    entry = remote / key[:2] / key
    remote_entry = open_current(entry)
    if damage == "evicted":
        remote_entry.path.chmod(0o700)
        (remote_entry.path / "result.json").unlink()
    elif damage == "partial":
        (entry / "current").chmod(0o600)
        (entry / "current").write_text('{"schema":')
    else:
        from rvw.results.generation import publish
        def wrong_key(directory):
            (directory / ".rvw-cache-key").write_text("d" * 64)
            (directory / "result.json").write_text('{"status":"pass"}')
        publish(entry, wrong_key)
    assert Cache(tmp_path / "third").get(key) is None


def test_retention_capacity_age_invalid_and_unowned(tmp_path):
    from rvw.regress.remote_cache import evict
    source = tmp_path / 'source'; source.mkdir()
    (source / 'result.json').write_text('{"status":"pass"}')
    cache = Cache(tmp_path / 'cache-root')
    for key in ('1'*64, '2'*64, '3'*64):
        cache.put(key, source)
    os.utime(cache.path('1'*64) / 'current', (1, 1))
    reader = open_current(cache.path('2'*64))
    (reader.path / 'result.json').chmod(0o600)
    (reader.path / 'result.json').write_text('corrupt')
    unowned = cache.dir / 'ff' / ('f'*64)
    unowned.mkdir(parents=True); (unowned / 'keep').touch()
    report = evict(cache.dir, max_bytes=0, max_age_s=100, now=200)
    assert {e['reason'] for e in report['removed']} == {'age', 'invalid', 'capacity'}
    assert report['retained_bytes'] == 0
    assert (unowned / 'keep').exists()
    assert Cache(tmp_path / 'cache-root').get('3'*64) is None


def test_native_resume_across_commands_and_repair(tmp_path, monkeypatch):
    import subprocess
    options = os.environ.get('RVW_TEST_SSH_OPTIONS')
    if not options:
        pytest.skip('native localhost SSH required')
    monkeypatch.setenv('RVW_CACHE_SSH_OPTIONS', options)
    remote = tmp_path / 'remote'
    monkeypatch.setenv('RVW_REMOTE_CACHE', 'localhost:' + str(remote))
    source = tmp_path / 'source'; source.mkdir()
    (source / 'result.json').write_text('{"status":"pass"}')
    (source / 'wave').write_bytes(os.urandom(512*1024))
    key = 'e'*64
    Cache(tmp_path / 'publisher').put(key, source)
    assert json.loads((remote / key[:2] / key / '.rvw-owner.json').read_text())['key'] == key
    local = tmp_path / 'reader'
    # Stop a real native rsync transfer. A second Python command must resume it.
    code = '''import sys
from pathlib import Path
from rvw.regress.store import Cache
from rvw.regress import remote_cache
from rvw.common.proc import run_group
original = remote_cache.run_group
def interrupt(argv, **kw):
    if argv[0] == 'rsync':
        argv = [*argv[:1], '--bwlimit=50', *argv[1:]]
        kw['timeout'] = .6
    return original(argv, **kw)
remote_cache.run_group = interrupt
assert Cache(Path(sys.argv[1])).get(sys.argv[2]) is None
'''
    subprocess.run([sys.executable, '-c', code, str(local), key], check=True, timeout=15)
    stages = list((local / 'cache/.downloads').glob('*/generations/*'))
    assert stages, 'interrupted transfer must retain partial generation bytes'
    # Same-size and same-mtime corruption must not bypass checksum repair.
    remote_reader = open_current(remote / key[:2] / key)
    result = stages[0] / 'result.json'
    assert result.exists()
    result.chmod(0o600)
    result.write_bytes(b'x' * result.stat().st_size)
    stamp = (remote_reader.path / 'result.json').stat()
    os.utime(result, (stamp.st_atime, stamp.st_mtime))
    partial_files = [p for stage in stages for p in stage.rglob('*') if p.is_file() and p.name == 'wave']
    if partial_files:
        partial_files[0].chmod(0o600)
        partial_files[0].write_bytes(b'bad')
    subprocess.run([sys.executable, '-c', 'from pathlib import Path; from rvw.regress.store import Cache; import sys; assert Cache(Path(sys.argv[1])).get(sys.argv[2]) is not None', str(local), key], check=True, timeout=20)
    reader = open_current(Cache(local).path(key))
    assert reader.read_bytes('wave') == (source / 'wave').read_bytes()
    assert not list((local / 'cache/.downloads').glob('*/generations'))
    import shlex
    command = [sys.executable, '-m', 'rvw.regress.remote_cache', '--root', str(remote),
               '--max-bytes', '0', '--max-age-s', '2592000']
    reply = subprocess.run(['ssh', *json.loads(options), 'localhost', shlex.join(command)],
                           check=True, capture_output=True, text=True, timeout=15)
    assert json.loads(reply.stdout)['retained_bytes'] == 0
    assert Cache(tmp_path / 'after-eviction').get(key) is None
