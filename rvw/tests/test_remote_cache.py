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
