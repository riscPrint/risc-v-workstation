"""Dataclasses, load/save and validation for the shared result formats in
`docs/PLATFORM_CONTRACTS.md`: rvw.run/1 (C1), rvw.results/1 (C3) and rvw.verdict/2 (C4).

Unknown keys are kept in `extra` so a file written by a newer tool survives a load/save round trip.
"""
from __future__ import annotations

import contextvars
import dataclasses
import json
import os
import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .generation import Generation, GenerationError, has_store, locate, open_current, open_generation
from rvw.common.capture import Capture, read_stable

from .signature import WALL_CLOCK, run_signature

RUN_SCHEMA = "rvw.run/1"
RESULTS_SCHEMA = "rvw.results/1"
VERDICT_SCHEMA = "rvw.verdict/2"
RUN_SET_SCHEMA = "rvw.regress-run/1"  # DIR/run.json of `rvw regress run` (rvw.regress.store)

STATUSES = ("pass", "fail", "timeout", "assert", "rvfi_error", "error")
FAILING = frozenset(s for s in STATUSES if s != "pass")
VERDICTS = ("accept", "reject", "inconclusive")


def inconclusive_cause(status: str | None, extra: dict, signature: str | None = None) -> str | None:
    """The shared conclusiveness rule, for C1 results and C3 entries alike: why a result
    neither shows nor rules out a failure, or None when it is evidence. Such a result is never a
    pass, never a reproduction and never a non-reproduction, whatever its status or signature:

    - an adapter `inconclusive` mark (a reason, or true);
    - a harness `error` (the adapter could not run the test; its message is about the harness);
    - a result rvw wrote itself because the adapter gave none (`synthesized`);
    - a wall-clock timeout (`wall_clock_timeout`, or the `timeout:wall-clock` signature);
    - pending or unattributed concurrent failures in RiscvSim's `details`.

    Used by `RunResult.why_inconclusive`, `TestEntry.conclusive` and through them by regress
    (resume, cache, compare), reduce, bisect and bundle."""
    why = extra.get("inconclusive")
    if isinstance(why, str) and why.strip():
        return why.strip()
    if why:
        return "the adapter marked the result inconclusive"
    details = extra.get("details")
    details = details if isinstance(details, dict) else {}
    sr = details.get("serial_rerun")
    if isinstance(sr, dict) and sr.get("attributed") is False:
        return "failure while other simulations ran; the serial rerun could not attribute it to this test"
    if details.get("concurrent") is True and status in ("assert", "rvfi_error") and not isinstance(sr, dict):
        return "failure while other simulations ran; attribution pending (no serial rerun result)"
    if status == "error":
        return "harness error: the adapter could not run the test"
    if extra.get("synthesized"):
        return "no result from the adapter: rvw wrote this one"
    if extra.get("wall_clock_timeout") or signature == WALL_CLOCK:
        return "wall-clock timeout: machine load or a hung process, not the core"
    return None

class SchemaError(ValueError):
    """A file does not follow its contract."""

    def __init__(self, errors: list[str], where: str = ""):
        self.errors = errors
        super().__init__((f"{where}: " if where else "") + "; ".join(errors))


def _split(cls, d: dict) -> tuple[dict, dict]:
    names = {f.name for f in dataclasses.fields(cls)} - {"extra"}
    known = {k: v for k, v in d.items() if k in names}
    extra = {k: v for k, v in d.items() if k not in names}
    return known, extra


def _to_dict(obj) -> dict:
    d = {}
    for f in dataclasses.fields(obj):
        if f.name == "extra":
            continue
        v = getattr(obj, f.name)
        if isinstance(v, list):
            v = [x.to_dict() if hasattr(x, "to_dict") else x for x in v]
        d[f.name] = v
    d.update(obj.extra)
    return d


def write_json(path: str | os.PathLike, obj: Any) -> None:
    """Write JSON atomically (temp file + rename), so readers never see half a file."""
    text = json.dumps(obj, indent=2, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


_READ_GENERATION = contextvars.ContextVar("results_generation", default=None)
_READ_CAPTURE = contextvars.ContextVar("results_capture", default=None)


def _read_json(path: Path, *, origin: list[Path] | None = None) -> dict:
    generation = _READ_GENERATION.get()
    capture = _READ_CAPTURE.get()
    if generation is not None and path.is_relative_to(generation.path):
        d = json.loads(generation.read_bytes(path.relative_to(generation.path)))
        resolved = path
    elif capture is not None:
        item = capture.file(path)
        d = json.loads(item.copy.read_bytes())
        resolved = Path(item.resolved)
    else:
        resolved = path.resolve(strict=True)
        d = json.loads(read_stable(resolved, keep=True)[3])
    if origin is not None:
        origin.append(resolved)
    if not isinstance(d, dict):
        raise SchemaError(["top level is not an object"], str(path))
    return d


# ---------------------------------------------------------------- C1: rvw.run/1

@dataclass
class RunResult:
    status: str
    core: str = ""
    config: str = ""
    elf: str = ""
    elf_sha256: str | None = None
    seed: int | None = None
    max_cycles: int | None = None
    mem_latency: int | None = None
    fail_code: int | None = None
    message: str | None = None
    cycles: int | None = None
    instret: int | None = None
    wall_s: float | None = None
    source: dict = field(default_factory=dict)
    tools: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    replay: str | None = None
    schema: str = RUN_SCHEMA
    extra: dict = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False)  # run directory it was loaded from

    @classmethod
    def from_dict(cls, d: dict, path: Path | None = None) -> "RunResult":
        errors = validate_run(d)
        if errors:
            raise SchemaError(errors)
        known, extra = _split(cls, d)
        known.pop("path", None)
        if "path" in d:
            extra["path"] = d["path"]
        return cls(**known, extra=extra, path=path)

    def to_dict(self) -> dict:
        d = _to_dict(self)
        d.pop("path", None)
        if "path" in self.extra:
            d["path"] = self.extra["path"]
        return d

    @property
    def dir(self) -> Path | None:
        return self.path

    @property
    def metrics(self) -> dict:
        m = self.extra.get("metrics")
        return m if isinstance(m, dict) else {}

    @property
    def details(self) -> dict:
        d = self.extra.get("details")
        return d if isinstance(d, dict) else {}

    @property
    def failed(self) -> bool:
        return self.status != "pass"

    @property
    def wall_clock_timeout(self) -> bool:
        """A timeout of the wall clock (machine load, a hung process), not of the simulated cycles."""
        return self.status == "timeout" and bool(self.extra.get("wall_clock_timeout"))

    @property
    def why_inconclusive(self) -> str | None:
        """Why this result neither shows nor rules out a failure, or None."""
        return inconclusive_cause(self.status, self.extra, run_signature(self))

    def get(self, key: str, default=None):
        """A top-level key of the JSON, known field or extra."""
        if key in self.extra:
            return self.extra[key]
        if key in {f.name for f in dataclasses.fields(self)} - {"extra", "path"}:
            v = getattr(self, key)
            return default if v is None else v
        return default

    def artifact(self, name: str) -> Path | None:
        """Absolute path of an artifact (`log`, `rvfi_trace`, `wave`, `konata`, `coverage`, ...) if it
        exists; falls back to the conventional file names."""
        if self.path is None:
            return None
        rel = self.artifacts.get(name)
        cands = [rel] if rel else []
        cands += {"wave": ["wave.vcd", "wave.fst", "wave.vcd.gz"], "rvfi_trace": ["rvfi.jsonl"],
                  "log": ["run.log"], "konata": ["konata.log"], "coverage": ["coverage.dat"]}.get(name, [])
        for c in cands:
            p = Path(c) if os.path.isabs(c) else self.path / c
            if p.exists():
                return p
        return None


def validate_run(d: Any) -> list[str]:
    e: list[str] = []
    if not isinstance(d, dict):
        return ["not an object"]
    if d.get("schema") != RUN_SCHEMA:
        e.append(f"schema is {d.get('schema')!r}, expected {RUN_SCHEMA!r}")
    if d.get("status") not in STATUSES:
        e.append(f"status {d.get('status')!r} not one of {', '.join(STATUSES)}")
    for k in ("seed", "max_cycles", "mem_latency", "fail_code", "cycles", "instret"):
        if d.get(k) is not None and (not isinstance(d[k], int) or isinstance(d[k], bool)):
            e.append(f"{k} must be an integer or null")
    wall = d.get("wall_s")
    if wall is not None:
        try:
            valid_wall = (isinstance(wall, (int, float)) and not isinstance(wall, bool)
                          and math.isfinite(wall) and wall >= 0)
        except OverflowError:
            valid_wall = False
        if not valid_wall:
            e.append("wall_s must be a finite non-negative number or null")
    if "inconclusive" in d and not isinstance(d["inconclusive"], (str, bool)):
        e.append("inconclusive must be a string (the reason) or a boolean")
    for k in ("source", "tools", "artifacts"):
        if k in d and not isinstance(d[k], dict):
            e.append(f"{k} must be an object")
    return e


def load_run(path: str | os.PathLike) -> RunResult:
    """Load a C1 result from `DIR/result.json` or the file itself. `.path` is the run directory
    (resolved). The canonical C1 loader: other tools use this one."""
    p = Path(path)
    if p.is_dir():
        p = p / "result.json"
    if not p.is_file():
        raise FileNotFoundError(f"{p}: no result.json (expected a C1 run directory)")
    origin = []
    d = _read_json(p, origin=origin)
    try:
        return RunResult.from_dict(d, path=origin[0].parent)
    except SchemaError as ex:
        raise SchemaError(ex.errors, str(p)) from None


def save_run(run: RunResult, path: str | os.PathLike) -> Path:
    p = Path(path)
    if p.suffix != ".json":
        p = p / "result.json"
    write_json(p, run.to_dict())
    return p


# ---------------------------------------------------------------- C3: rvw.results/1

@dataclass
class TestEntry:
    id: str
    status: str
    seed: int | None = None
    cycles: int | None = None
    instret: int | None = None
    wall_s: float | None = None
    run: str | None = None
    signature: str | None = None
    metrics: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    __test__ = False  # not a pytest class

    @classmethod
    def from_dict(cls, d: dict) -> "TestEntry":
        known, extra = _split(cls, d)
        return cls(**known, extra=extra)

    def to_dict(self) -> dict:
        return _to_dict(self)

    @property
    def failed(self) -> bool:
        return self.status != "pass"

    @property
    def conclusive(self) -> bool:
        """False when the entry says nothing about the core: a harness error, a result rvw wrote
        because the adapter did not (`synthesized`), or a wall-clock timeout. Such an entry never
        counts as the same failure as the base, nor as a known failure. `inconclusive` (a reason)
        marks a result the adapter could not attribute (`RunResult.why_inconclusive`)."""
        return inconclusive_cause(self.status, self.extra, self.signature) is None


@dataclass
class SuiteResults:
    run_id: str
    suite: str
    core: str
    config: str
    created: str
    source: dict = field(default_factory=dict)
    tests: list[TestEntry] = field(default_factory=list)
    schema: str = RESULTS_SCHEMA
    extra: dict = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False)  # directory it was loaded from
    generation: str | None = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, d: dict, path: Path | None = None) -> "SuiteResults":
        errors = validate_results(d)
        if errors:
            raise SchemaError(errors, str(path or ""))
        known, extra = _split(cls, d)
        known.pop("path", None)
        known.pop("generation", None)
        known["tests"] = [TestEntry.from_dict(t) for t in known.get("tests", [])]
        return cls(**known, extra=extra, path=path)

    def to_dict(self) -> dict:
        d = _to_dict(self)
        d.pop("path", None)
        d.pop("generation", None)
        return d

    def counts(self) -> dict[str, int]:
        c = {s: 0 for s in STATUSES}
        for t in self.tests:
            c[t.status] = c.get(t.status, 0) + 1
        return {k: v for k, v in c.items() if v}


def validate_results(d: Any) -> list[str]:
    e: list[str] = []
    if not isinstance(d, dict):
        return ["not an object"]
    if d.get("schema") != RESULTS_SCHEMA:
        e.append(f"schema is {d.get('schema')!r}, expected {RESULTS_SCHEMA!r}")
    for k in ("run_id", "suite", "core", "config", "created"):
        if not isinstance(d.get(k), str):
            e.append(f"{k} must be a string")
    if not isinstance(d.get("tests"), list):
        e.append("tests must be a list")
        return e
    for i, t in enumerate(d["tests"]):
        if not isinstance(t, dict):
            e.append(f"tests[{i}] is not an object")
            continue
        if not isinstance(t.get("id"), str):
            e.append(f"tests[{i}].id must be a string")
        if t.get("status") not in STATUSES:
            e.append(f"tests[{i}].status {t.get('status')!r} not one of {', '.join(STATUSES)}")
        if t.get("status") != "pass" and t.get("status") in STATUSES and not t.get("signature"):
            e.append(f"tests[{i}] failed without a signature")
        if "metrics" in t and not isinstance(t["metrics"], dict):
            e.append(f"tests[{i}].metrics must be an object")
    return e


def load_results(path: str | os.PathLike, *, generation: Generation | None = None,
                 capture: Capture | None = None) -> SuiteResults:
    """Load C3 through its owner. Accept a pinned reader or a command-owned input capture."""
    p = Path(path)
    if p.is_dir():
        p = p / "results.json"
    absolute = Path(os.path.abspath(p))
    if capture is not None:
        item = capture.file(absolute)
        owner = _nearest_manifest(absolute.parent)
        canonical_owner = _nearest_manifest(Path(item.resolved).parent)
        if (owner.resolve() if owner else None) != canonical_owner:
            raise SchemaError(["results path changes its owning run set through an alias"], str(path))
        root = owner or absolute.parent
        tree = capture.tree(root, git=False)
        result = load_results(tree.copy / absolute.relative_to(root))
        result.path = absolute.parent  # Artifacts remain relative to the logical input directory.
        return result
    if _READ_GENERATION.get() is None:
        try:
            selected, generation = ((absolute, generation) if generation is not None else locate(absolute))
            if generation is not None:
                for result in _generation_results(generation):
                    if result.path == selected.parent:
                        return result
                raise SchemaError(["the owning run set does not list this results directory"], str(path))
        except GenerationError as exc:
            raise SchemaError([str(exc)], str(path)) from exc
    requested_owner = _nearest_manifest(Path(os.path.abspath(p)).parent)
    p = p.resolve()
    res = _read_results(p)
    owner = _results_owner(res)
    runner_origin = isinstance(res.source, dict) and {"tools_key", "adapter"} <= res.source.keys()
    if requested_owner is None and ("run_set" in res.extra or runner_origin):
        raise SchemaError(["the owning run set is missing above the requested path"], str(path))
    if requested_owner is not None and owner != requested_owner.resolve():
        raise SchemaError(["the results path changes its owning run set through an alias"], str(path))
    if owner is None:
        return res
    for member in load_run_set(owner):
        if member.path == res.path:
            return member
    raise SchemaError(["the owning run set does not list this results directory"], str(p))


def _read_results(path: Path) -> SuiteResults:
    """Internal parse only. Public readers must use load_results or load_run_set."""
    origin = []
    data = _read_json(path, origin=origin)
    return SuiteResults.from_dict(data, path=origin[0].parent)


def _nearest_manifest(d: Path) -> Path | None:
    return next((parent for parent in (d, *d.parents) if os.path.lexists(parent / "run.json")), None)


def _results_owner(res: SuiteResults) -> Path | None:
    d = res.path.resolve()
    owner = _nearest_manifest(d)
    if "run_set" in res.extra:
        rel = res.extra["run_set"]
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
            raise SchemaError(["run_set must be a relative directory path"], str(d))
        expected = (d / rel).resolve()
        if expected != d and expected not in d.parents:
            raise SchemaError(["run_set must name this directory or an ancestor"], str(d))
        if owner != expected:
            raise SchemaError(["the owning run set is missing or disagrees with run_set"], str(d))
    elif (owner is None and isinstance(res.source, dict)
          and {"tools_key", "adapter"} <= res.source.keys()):
        raise SchemaError(["the owning run set is missing for this runner result"], str(d))
    elif owner is None and d.name == res.config and d.parent.name == res.suite:
        # Older runner output has no run_set field. Its job records still identify the layout.
        for test in res.tests:
            run = Path(test.run) if isinstance(test.run, str) else None
            if (run is not None and not run.is_absolute() and ".." not in run.parts
                    and (d / run.parent / ".rvw-job.json").is_file()):
                raise SchemaError(["the owning run set is missing for this runner suite"], str(d))
    return owner


def save_results(res: SuiteResults, directory: str | os.PathLike) -> Path:
    p = Path(directory) / "results.json"
    write_json(p, res.to_dict())
    res.path = p.parent
    return p


def find_results(root: str | os.PathLike) -> list[SuiteResults]:
    """All C3 results under `root` (a results dir itself, or a tree holding several).

    A run set (a directory with a `rvw.regress-run/1` run.json) is read through its manifest: only
    the suites its current run.json lists, never other results.json left in a reused output
    directory. An incomplete run set (not finished) or one whose files disagree with the manifest
    raises SchemaError: comparing it could judge stale or partial evidence.

    The manifest wins at every level (review 14): a directory holding both a run-set run.json and a
    results.json its manifest does not list (an old C3 file left in a reused output directory) is
    refused, never read as either."""
    root = Path(root)
    if _private_store(root):
        return []
    if _is_run_set(root):
        return load_run_set(root)
    if (root / "results.json").is_file():
        return [load_results(root)]
    found: list[SuiteResults] = []

    def walk(d: Path) -> None:
        for child in sorted(d.iterdir()):
            if child.is_symlink() or not child.is_dir():
                continue
            if _private_store(child):
                continue
            if _is_run_set(child):
                found.extend(load_run_set(child))
            elif (child / "results.json").is_file():
                found.append(load_results(child))  # nothing nested inside a results dir counts
            else:
                walk(child)

    walk(root)
    return found


def _private_store(directory):
    inputs = (directory / ".rvw-private-inputs").is_file()
    cache = (directory / ".rvw-cache-entry").is_file()
    if not inputs and not cache:
        return False
    conflict = (directory / "run.json").exists() or (directory / "results.json").exists()
    if has_store(directory):
        reader = open_current(directory)
        conflict |= any(name == "run.json" or Path(name).name == "results.json"
                        for name, _, _, _ in reader.files)
    if inputs:
        allowed = {".rvw-private-inputs", "capture", "resume-capture", "work", "bin"}
        conflict |= any(child.name not in allowed for child in directory.iterdir())
    if conflict:
        raise SchemaError(["private input/cache marker conflicts with a run set"], str(directory))
    return True


def _is_run_set(d: Path) -> bool:
    if (d / ".rvw-cache-entry").is_file():
        return False
    if has_store(d):
        return True
    rj = d / "run.json"
    if not rj.is_file():
        return False
    try:
        return _read_json(rj).get("schema") == RUN_SET_SCHEMA
    except (OSError, ValueError, AttributeError):
        raise SchemaError(["unreadable run.json"], str(rj)) from None


def _lists_itself(manifest: dict) -> bool:
    """True when a run set's manifest lists its own directory (path ".") as a suite's results."""
    entries = manifest.get("results") if isinstance(manifest, dict) else None
    return isinstance(entries, list) and any(
        isinstance(e, dict) and isinstance(e.get("path"), str) and e["path"] and Path(e["path"]) == Path(".")
        for e in entries)


def _check_not_stale(d: Path) -> None:
    """Refuse a results.json that sits beside a run-set run.json which does not list it: the file is
    left over from an earlier run (review 14) and may hide the run set's current failures."""
    if not ((d / "results.json").is_file() and _is_run_set(d)):
        return
    if not _lists_itself(_read_json(d / "run.json")):
        raise SchemaError(["the directory holds both a run set (run.json) and a results.json its manifest "
                           "does not list: the results.json is stale; remove it, or rerun into a new --out"],
                          str(d / "results.json"))


def _generation_results(generation):
    token = _READ_GENERATION.set(generation)
    try:
        results = _load_run_set(generation.path)
        for result in results:
            result.generation = generation.id
        return results
    finally:
        _READ_GENERATION.reset(token)


def load_run_set(directory: str | os.PathLike | Generation) -> list[SuiteResults]:
    """Load a complete run set, optionally through an already pinned generation."""
    if isinstance(directory, Generation):
        return _generation_results(directory)
    directory = Path(directory).resolve()
    if has_store(directory) and os.path.lexists(directory / "results.json"):
        raise SchemaError(["the results.json is stale beside a result generation store; "
                           "remove it, or rerun into a new --out"], str(directory / "results.json"))
    try:
        if os.path.lexists(directory / "current"):
            return _generation_results(open_current(directory))
        if (directory / "generation.json").is_file() and directory.parent.name == "generations":
            return _generation_results(open_generation(directory.parent.parent, directory.name))
        if (directory / "generations").exists():
            raise GenerationError("result generations exist but current is missing; refusing legacy fallback")
        # Legacy manifests have no content binding. Capture their JSON under the writer's
        # ownership lock. A live writer or orphan adapter refuses this compatibility route.
        from rvw.regress.runner import out_lock
        with out_lock(directory), tempfile.TemporaryDirectory(prefix="rvw-legacy-results-") as temporary:
            capture = Capture(Path(temporary) / "capture")
            token = _READ_CAPTURE.set(capture)
            try:
                return _load_run_set(directory)
            finally:
                _READ_CAPTURE.reset(token)
    except GenerationError as exc:
        raise SchemaError([str(exc)], str(directory)) from exc


def _load_run_set(directory: str | os.PathLike) -> list[SuiteResults]:
    """The suites a run set's run.json lists, checked against it (see find_results)."""
    d = Path(directory).resolve()
    rj = d / "run.json"
    m = _read_json(rj)
    where = str(rj)
    if m.get("schema") != RUN_SET_SCHEMA:
        raise SchemaError([f"schema is {m.get('schema')!r}, expected {RUN_SET_SCHEMA!r}"], where)
    _check_not_stale(d)
    if not isinstance(m.get("finished"), str) or not m["finished"].strip():
        raise SchemaError(["the run set is incomplete (no `finished` time: the run stopped or is still "
                           "running); resume it with `rvw regress run --out` before comparing"], where)
    entries = m.get("results")
    if not isinstance(entries, list):
        raise SchemaError(["results must be a list"], where)
    src = m.get("source")
    if not isinstance(src, dict) or not src:
        raise SchemaError(["run-set source identity must be a non-empty object"], where)
    out, errors, seen = [], [], set()
    for i, e in enumerate(entries):
        path = e.get("path") if isinstance(e, dict) else None
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            errors.append(f"results[{i}].path must be a relative path inside the run set")
            continue
        target = (d / path).resolve()
        if not target.is_relative_to(d):
            errors.append(f"results[{i}]: {path} escapes the run set")
            continue
        if target in seen:
            errors.append(f"results[{i}]: {path} is listed twice")
            continue
        seen.add(target)
        rf = (target / "results.json").resolve()
        if not rf.is_relative_to(d):
            errors.append(f"results[{i}]: {path}/results.json escapes the run set")
            continue
        if not rf.is_file():
            errors.append(f"results[{i}]: {path}/results.json is missing")
            continue
        res = _read_results(rf)
        if _results_owner(res) != d:
            errors.append(f"{path}/results.json: owning run set disagrees with this manifest")
        for key, have, want in (("run_id", res.run_id, m.get("run_id")), ("suite", res.suite, e.get("suite")),
                                ("config", res.config, e.get("config")), ("tests", len(res.tests), e.get("tests"))):
            if have != want:
                errors.append(f"{path}/results.json: {key} is {have!r}, the manifest says {want!r}")
        if "core" in m and res.core != m["core"]:
            errors.append(f"{path}/results.json: core disagrees with the manifest")
        for key in src.keys() & res.source.keys():
            if res.source[key] != src[key]:
                errors.append(f"{path}/results.json: source.{key} is {res.source[key]!r}, the run set's is {src[key]!r}")
        # Older C3 files kept only a short revision and dirty bit. Do not discard the manifest's
        # full source identity when comparing a tree of those run sets (review 15).
        res.source = {**src, **res.source}
        out.append(res)
    if errors:
        raise SchemaError(["inconsistent run set: " + "; ".join(errors)], where)
    return out


# ---------------------------------------------------------------- C4: rvw.verdict/2

@dataclass
class Verdict:
    verdict: str  # "accept" | "reject" | "inconclusive"
    new_failures: list[dict] = field(default_factory=list)
    fixed: list[dict] = field(default_factory=list)
    known_failures: list[dict] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    perf: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    inconclusive: list[dict] = field(default_factory=list)  # candidate results that prove nothing
    schema: str = VERDICT_SCHEMA
    extra: dict = field(default_factory=dict)
    tests: str = "incomplete"  # comparison outcome, independent of committed-source policy
    not_accepted_reason: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Verdict":
        errors = validate_verdict(d)
        if errors:
            raise SchemaError(errors)
        known, extra = _split(cls, d)
        return cls(**known, extra=extra)

    def to_dict(self) -> dict:
        return _to_dict(self)

    @property
    def accepted(self) -> bool:
        return self.verdict == "accept"

    @property
    def exit_code(self) -> int:
        """0 accept, 1 reject, 3 inconclusive (2 stays a usage or config error)."""
        return {"accept": 0, "reject": 1}.get(self.verdict, 3)


def validate_verdict(d: Any) -> list[str]:
    e: list[str] = []
    if not isinstance(d, dict):
        return ["not an object"]
    if d.get("schema") != VERDICT_SCHEMA:
        e.append(f"schema is {d.get('schema')!r}, expected {VERDICT_SCHEMA!r}")
    if d.get("verdict") not in VERDICTS:
        e.append("verdict must be 'accept', 'reject' or 'inconclusive'")
    if d.get("tests") not in ("pass", "fail", "incomplete"):
        e.append("tests must be 'pass', 'fail' or 'incomplete'")
    if d.get("not_accepted_reason") not in (None, "uncommitted"):
        e.append("not_accepted_reason must be null or 'uncommitted'")
    if d.get("verdict") == "accept" and (d.get("tests") != "pass" or d.get("not_accepted_reason") is not None):
        e.append("accept requires tests pass and no not_accepted_reason")
    for k in ("new_failures", "fixed", "known_failures", "missing", "perf", "reasons", "inconclusive"):
        if k in d and not isinstance(d[k], list):
            e.append(f"{k} must be a list")
    return e


def load_verdict(path: str | os.PathLike) -> Verdict:
    p = Path(path)
    if p.is_dir():
        p = p / "verdict.json"
    return Verdict.from_dict(_read_json(p))


def validate(d: Any) -> list[str]:
    """Validate any contract object by its `schema` key."""
    schema = d.get("schema") if isinstance(d, dict) else None
    fn = {RUN_SCHEMA: validate_run, RESULTS_SCHEMA: validate_results, VERDICT_SCHEMA: validate_verdict}.get(schema)
    return fn(d) if fn else [f"unknown schema {schema!r}"]
