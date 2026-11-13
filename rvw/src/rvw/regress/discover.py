"""Expand a suite into its tests."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import ConfigError, Suite


@dataclass(frozen=True)
class TestSpec:
    id: str
    elf: Path | None  # None for kind = "build"

    __test__ = False


def discover(suite: Suite, include: list[str] | None = None) -> list[TestSpec]:
    """Tests of a suite, sorted by id. `include` adds regexes that must also match (a filter)."""
    if suite.kind == "build":
        return [TestSpec("build", None)]
    if suite.dir is None or not suite.dir.is_dir():
        raise ConfigError(f"suite {suite.name}: test directory {suite.dir} does not exist")
    if suite.act4_manifest:
        from .act4 import verify_manifest
        try:
            verify_manifest(suite.act4_manifest, suite.dir)
        except (ValueError, OSError, KeyError) as exc:
            raise ConfigError(f"suite {suite.name}: {exc}") from exc
    inc = [re.compile(r) for r in suite.include]
    exc = [re.compile(r) for r in suite.exclude]
    extra = [re.compile(r) for r in (include or [])]
    tests = []
    for f in suite.dir.glob(suite.glob):
        if not f.is_file():
            continue
        tid = f.relative_to(suite.dir).as_posix()
        if suite.strip_suffix and tid.endswith(suite.strip_suffix):
            tid = tid[: -len(suite.strip_suffix)]
        if inc and not any(r.search(tid) for r in inc):
            continue
        if any(r.search(tid) for r in exc):
            continue
        tests.append(TestSpec(tid, f.absolute()))
    # Before the run's own filter: the suite's tests, not this run's subset, must be distinct.
    check_ids(suite.name, tests)
    tests = [t for t in tests if all(r.search(t.id) for r in extra)]
    return sorted(tests, key=lambda t: t.id)


def path_key(rel: str) -> tuple[str, ...]:
    """How a relative output path compares on any file system rvw writes to: by component, after
    Unicode NFC and case folding (macOS file systems ignore case; a set copied there must not
    merge two directories)."""
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in rel.split("/"))


def check_ids(suite: str, tests: list[TestSpec]) -> None:
    """Each test writes `tests/<id>/` (and `tests/<id>/seed-<n>/`): two tests with one id (`foo`
    and `foo.elf` with strip_suffix `.elf`, or ids differing only in case) would share a
    directory and one result could hide the other's failure (review 13); a test inside another
    test's directory (`a` and `a/b`, or `a/seed-2`) is deleted or overwritten when the outer one
    runs. Both are a config error, found before any adapter starts."""
    seen: dict[tuple[str, ...], TestSpec] = {}
    for t in sorted(tests, key=lambda t: (t.id, str(t.elf))):
        k = path_key(t.id)
        if k in seen:
            o = seen[k]
            raise ConfigError(f"suite {suite}: tests {o.id!r} ({o.elf}) and {t.id!r} ({t.elf}) have the same "
                              "output directory (same id after strip_suffix, or ids differing only in case); "
                              "rename one or exclude it")
        seen[k] = t
    for k, t in seen.items():
        for i in range(1, len(k)):
            o = seen.get(k[:i])
            if o is not None:
                raise ConfigError(f"suite {suite}: test {t.id!r} ({t.elf}) would be written inside the output "
                                  f"directory of test {o.id!r} ({o.elf}); rename one or exclude it")
