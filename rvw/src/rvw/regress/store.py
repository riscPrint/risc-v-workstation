"""The results root (`$RVW_RESULTS`, default `~/.cache/rvw/results`):

    index.jsonl          one line per suite run set (`rvw regress history` reads it)
    runs/<run_id>/       default output of `rvw regress run` and `gate`
    cache/<kk>/<key>/    finished test directories, keyed by everything that determines the result
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from rvw.results.generation import publish, open_current
from pathlib import Path

from rvw.results.schema import RUN_SET_SCHEMA  # noqa: F401 (re-exported)


def results_root() -> Path:
    return Path(os.environ.get("RVW_RESULTS", Path.home() / ".cache" / "rvw" / "results"))


def index_path(root: Path | None = None) -> Path:
    return (root or results_root()) / "index.jsonl"


def append_index(entry: dict, root: Path | None = None) -> None:
    p = index_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def read_file(path: Path) -> bytes:
    """Read a regular file once. The nonblocking open keeps a FIFO from hanging the reader."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"{path} is not a regular file")
        return f.read()


def read_index(root: Path | None = None) -> list[dict]:
    """Index entries, oldest first. A run that was indexed twice (resumed) keeps its last entry."""
    p = index_path(root)
    if not p.is_file():
        return []
    by_path: dict[str, dict] = {}
    lines = read_file(p).decode().splitlines()
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(e, dict) and "path" in e:
            by_path.pop(e["path"], None)
            by_path[e["path"]] = e
    return list(by_path.values())


def resolve_run(ref: str, root: Path | None = None, *, core: str | None = None) -> Path:
    """A results path, run id/prefix or `latest`; indexed lookup can be scoped by core name."""
    p = Path(ref).expanduser()
    if p.exists():
        return p.resolve()
    entries = read_index(root)
    if core is not None:
        entries = [e for e in entries if e.get("core") == core]
    if ref == "latest" and entries:
        return Path(entries[-1]["path"])
    hits = [e for e in entries if e.get("run_id") == ref] or [e for e in entries if e.get("run_id", "").startswith(ref)]
    if len({e["path"] for e in hits}) == 1:
        return Path(hits[0]["path"])
    if hits:
        raise ValueError(f"run {ref!r} is ambiguous: {', '.join(e['run_id'] for e in hits)}")
    scope = f" for core {core!r}" if core is not None else ""
    raise ValueError(f"no results directory or indexed run {ref!r}{scope}")


class Cache:
    def __init__(self, root: Path | None = None):
        self.dir = (root or results_root()) / "cache"
        self._readers = {}
        self.remote = os.environ.get("RVW_REMOTE_CACHE")

    def path(self, key: str) -> Path:
        return self.dir / key[:2] / key

    def get(self, key: str) -> Path | None:
        p = self.path(key)
        if not (p / "current").exists() and self.remote:
            import tempfile
            from .remote_cache import transfer
            with tempfile.TemporaryDirectory(prefix="rvw-cache-fetch-") as temp:
                stage = Path(temp)
                try:
                    if transfer(self.remote, key, stage):
                        self._put(key, open_current(stage).path)
                except (OSError, ValueError):
                    pass  # Transfer failure is a miss, never evidence.
        if not (p / "current").exists():
            return None  # Legacy cache has no generation binding. Re-run it.
        if key not in self._readers:
            self._readers[key] = open_current(p)
        return self._readers[key].path

    def load(self, key):
        from rvw.results import RunResult
        if self.get(key) is None:
            return None
        reader = self._readers[key]
        return RunResult.from_dict(json.loads(reader.read_bytes("result.json")), path=reader.path)

    def put(self, key: str, test_dir: Path) -> None:
        self._put(key, test_dir)
        if self.remote:
            from .remote_cache import transfer
            try:
                transfer(self.remote, key, self.path(key), upload=True)
            except (OSError, ValueError):
                pass  # A cache outage does not change the measured result.

    def _put(self, key: str, test_dir: Path) -> None:
        dest = self.path(key)
        if (dest / "current").exists():
            return
        dest.mkdir(parents=True, exist_ok=True)
        (dest / '.rvw-cache-entry').write_text('rvw.regress-cache/1\n')
        def build(directory):
            (directory / ".rvw-cache-key").write_text(key)
            for path in test_dir.rglob("*"):
                relative = path.relative_to(test_dir)
                if relative.as_posix() in ("generation.json", ".rvw-cache-key"):
                    continue
                if path.is_symlink():
                    raise ValueError("cache input contains a symlink")
                if path.is_dir():
                    (directory / relative).mkdir(parents=True, exist_ok=True)
                else:
                    (directory / relative).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, directory / relative)
        publish(dest, build)

    def restore(self, key: str, test_dir: Path) -> bool:
        root = self.path(key)
        if not (root / "current").exists():
            return False
        if self.get(key) is None:
            return False
        generation = self._readers[key]
        shutil.rmtree(test_dir, ignore_errors=True)
        for top, dirs, files in os.walk(generation.path):
            relative = Path(top).relative_to(generation.path)
            (test_dir / relative).mkdir(parents=True, exist_ok=True)
            for name in files:
                if relative == Path('.') and name == 'generation.json':
                    continue
                (test_dir / relative / name).write_bytes(generation.read_bytes(relative / name))
        return True
