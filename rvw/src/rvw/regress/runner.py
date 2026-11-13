"""Run suites through a core adapter (contract C1) and write C3 results.

Output layout of a run set (`--out DIR`):

    DIR/current                               atomic pointer to a sealed generation
    DIR/generations/<id>/run.json              captured source, suites and counts
    DIR/run.json                              mutable progress/workspace manifest
    DIR/<suite>/<config>/results.json          mutable C3 workspace copy
    DIR/<suite>/<config>/junit.xml
    DIR/<suite>/<config>/adapter.log          everything the adapter printed
    DIR/<suite>/<config>/tests/<id>/          one C1 run directory per test (result.json, ...)
    DIR/<suite>/<config>/tests/<id>/seed-<n>/ instead, when a test runs with several seeds
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import random
import re
import shlex
import shutil
import signal
import sys
import time
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import TextIO

from rvw.common import lock as locks
from rvw.common.lock import lock_dir
from rvw.common.capture import CaptureError
from rvw.results.generation import publish, open_current, GenerationError
from .captured import Inputs

from rvw.common.proc import run_group
from rvw.results import (RunResult, SchemaError, SuiteResults, TestEntry, load_run, run_signature,
                         save_results, save_run, write_json, write_junit)

from .config import ConfigError, CoreConfig, Suite, finite_number, positive_int
from .discover import TestSpec, discover, path_key
from .source import Source
from .store import RUN_SET_SCHEMA, Cache, append_index, read_file, read_index

JOB_FILE = ".rvw-job.json"
JOB_IDENTITY_VERSION = 10  # Complete RTL identities permit reuse across core commits.
RUN_OPTIONS = ("max_cycles", "mem_latency")  # C1 run options; they never change the built model
MESSAGE_MAX = 400


def _cache_record(capture):
    record = capture.record()
    # Git refs select report revisions. Job parameters identify sources or generated RTL.
    record.pop("git_refs", None)
    return record


def _cache_key(capture, options, *, complete):
    record = _cache_record(capture)
    if complete is not True or record["problems"]:
        return None
    payload = {"capture": record, "options": options}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _rtl_identity(document):
    """Only a complete RTL, clean harness and native tool identity can replace core revisions."""
    if not document:
        return False
    claims = document["result_claims"]
    return (all(isinstance(claims.get(key), str) and re.fullmatch(pattern, claims[key])
                for key, pattern in (("rtl_sha256", r"[0-9a-f]{64}"),
                                     ("source.tools_rev", r"[0-9a-f]{40}|[0-9a-f]{64}"),
                                     ("tools.native_build.sha256", r"[0-9a-f]{64}")))
            and claims.get("source.tools_dirty") is False
            and not any(key.startswith("source.core_") for key in claims))


@dataclass
class PlanItem:
    suite: Suite
    config: str
    include: list[str] = field(default_factory=list)
    seeds: int | None = None


@dataclass
class RunOptions:
    jobs: int | None = None
    seeds: int | None = None  # overrides the suite / tier seed count
    seed_base: int = 1
    random_seeds: bool = False
    include: list[str] = field(default_factory=list)
    max_cycles: int | None = None
    timeout_s: float | None = None
    replay_max_bytes: int | None = None  # defaults to the capture tree byte limit
    rvfi_trace: bool = False
    use_cache: bool = True
    fresh: bool = False
    tier: str | None = None
    label: str | None = None
    index: bool = True
    results_root: Path | None = None
    previous_generation: object | None = field(default=None, repr=False)
    log: TextIO | None = sys.stderr

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        # Shared by the CLI, MCP and the gate (review 11: `--seeds -1` ran zero jobs and succeeded;
        # `--seeds 0` silently fell back to the suite's count).
        positive_int(self.seeds, "seeds", optional=True)
        positive_int(self.jobs, "jobs", optional=True)
        positive_int(self.max_cycles, "max_cycles", optional=True)
        positive_int(self.replay_max_bytes, "replay_max_bytes", optional=True)
        finite_number(self.timeout_s, "timeout_s", positive=True, optional=True)
        if isinstance(self.seed_base, bool) or not isinstance(self.seed_base, int):
            raise ConfigError(f"seed_base must be a whole number, not {self.seed_base!r}")


@dataclass
class Job:
    suite: Suite
    config: str
    test: TestSpec
    seed: int
    dir: Path
    rel: str  # result.json path relative to the suite results dir
    options: dict
    params: dict
    key: str | None
    multi_seed: bool
    claims: dict


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _say(opts: RunOptions, msg: str) -> None:
    if opts.log:
        print(msg, file=opts.log, flush=True)


def _lookup_origin(d: dict, path: str):
    """Return the value and the actual fallback key consumed from C1."""
    for alt in path.split("|"):
        v = d
        for part in alt.strip().split("."):
            v = v.get(part) if isinstance(v, dict) else None
        if v is not None:
            return v, alt.strip()
    return None, None


def _seeds(n: int, opts: RunOptions, run_id: str, salt: str) -> list[int]:
    if opts.random_seeds:
        # Distinct: each seed has its own directory (seed-<n>).
        r = random.Random(f"{run_id}/{salt}")
        out: dict[int, None] = {}
        while len(out) < n:
            out[r.randrange(1, 2**31)] = None
        return list(out)
    return [opts.seed_base + i for i in range(n)]


def seed_count(item: PlanItem, opts: RunOptions) -> int:
    if item.suite.kind == "build":
        return 1
    for value, name in ((opts.seeds, "seeds"), (item.seeds, f"tier seeds of {item.suite.name}"),
                        (item.suite.seeds, f"seeds of suite {item.suite.name}")):
        if value is not None:
            return positive_int(value, name)
    return 1


def job_options(suite: Suite, opts: RunOptions) -> dict:
    options = {}
    max_cycles = opts.max_cycles or suite.max_cycles
    if max_cycles is not None:
        options["max_cycles"] = int(max_cycles)
    if suite.mem_latency is not None:
        options["mem_latency"] = int(suite.mem_latency)
    if opts.rvfi_trace:
        options["rvfi_trace"] = True
    return {**options, **suite.options}


class Runner:
    def __init__(self, core: CoreConfig, source: Source, out: Path, opts: RunOptions, *, capture=None):
        self.inputs = None
        try:
            self._initialize(core, source, out, opts, capture=capture)
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self.inputs is not None:
            self.inputs.close()

    def _initialize(self, core, source, out, opts, *, capture=None):
        core.validate()
        opts.validate()
        if source.path is not None:
            core.require_source_selection()
        self.core, self.source, self.out, self.opts = core, source, out.resolve(), opts
        self.cache = Cache(opts.results_root) if opts.use_cache else None
        self.inputs = Inputs(core, source, capture=capture)
        self.env = dict(self.inputs.child_env)
        self.adapter = self.inputs.adapter
        self.jobs = opts.jobs or core.jobs
        # The server builds its first model inside run-many. Preserve the build
        # budget that the skipped pre-build process would have had.
        self.startup_s = core.startup_s + (core.build_timeout_s if core.persistent and core.build_first else 0)
        def values(value):
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, dict):
                return {key: values(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [values(item) for item in value]
            return value
        self.config_values = values(asdict(core))
        self.config_values.pop("capture", None)
        python_environments = list(self.inputs.python_environments.values())
        self.tools_key = _cache_key(self.inputs.capture,
            {"config": core.capture, "effective_config": self.config_values,
             "python_environments": python_environments}, complete=not self.inputs.problem)
        self.adapter_id = {"argv": core.adapter, "capture": _cache_record(self.inputs.capture),
                           "python_environments": python_environments}
        self.identities = {}  # adapter `identity` arguments -> {"sha256", "document"}
        self.source_known = source.path is not None
        self.identity_complete = not self.inputs.problem
        self.cacheable = bool(self.source.rev) and not self.source.dirty and self.identity_complete
        self.nonce = None if self.identity_complete else os.urandom(8).hex()
        self.input_change = self.inputs.problem
        self.tools_dirty = False
        self.cache_pending = []
        self.suite_jobs = []
        self.start_record = self.inputs.record()
        self._out_lock = None
        self._found = None

    def _incomplete(self, why: str) -> None:
        """Mark the run set's identity incomplete: nothing runs, is resumed or is cached."""
        self.input_change = self.input_change or why
        self.identity_complete = self.cacheable = False
        self.nonce = self.nonce or os.urandom(8).hex()

    def _identity(self, config: str, options: dict) -> dict | None:
        """The adapter's identity for one model (contract C1). Called once per (config, model
        options) under the core lock, because it may elaborate the design. A plain adapter prints
        text once; its hash joins every job key. With `identity_capture`, the adapter prints an
        rvw.adapter-capture/2 document whose `result_claims` (for example the RTL hash) each C1
        result of that model must carry. If the adapter cannot tell, nothing is reused."""
        if not self.core.identity or self.inputs.problem:
            return None
        args = ["identity"]
        if self.core.identity_capture:
            model = {k: v for k, v in options.items() if k not in RUN_OPTIONS}
            args += ["--config", config, "--options", json.dumps(model, sort_keys=True)]
        memo = json.dumps(args)
        if memo in self.identities:
            return self.identities[memo]
        document, ok = None, False
        try:
            with locks.held(self.core.lock, self.core.lock_dir, log=self.opts.log):
                r = run_group([*self.adapter, *args], cwd=self.inputs.cwd, env=self.env, capture=True,
                              timeout=self.core.identity_timeout_s)
            text, ok = r.stdout or "", r.returncode == 0 and bool((r.stdout or "").strip())
            if not ok and r.stderr:
                _say(self.opts, r.stderr[:4000] + ('\n...\n' + r.stderr[-1500:] if len(r.stderr) > 5500 else r.stderr[4000:]))
            if ok and self.core.identity_capture:
                from .adapter_capture import accept
                document = accept(text, self.source.to_dict())
                keyed = document
                if _rtl_identity(document):
                    keyed = {**document, "source": {key: value for key, value in document["source"].items()
                                                    if not key.startswith("core_")}}
                text = json.dumps(keyed, sort_keys=True, allow_nan=False)
        except (OSError, ValueError, KeyError, TypeError) as e:
            text, ok = str(e), False
            _say(self.opts, f"rvw: input_not_captured:adapter_identity: {e}")
        if not ok:
            _say(self.opts, f"rvw: `{shlex.join([*self.adapter, *args])}` failed; no reuse of results")
            self._incomplete("input_not_captured:adapter_identity")
            identity = {"sha256": f"unavailable-{os.urandom(8).hex()}", "document": None}
        else:
            identity = {"sha256": hashlib.sha256(text.encode()).hexdigest(), "document": document}
            if document is not None and True in (document["result_claims"].get("source.tools_dirty"),
                                                 (document.get("source") or {}).get("tools_dirty")):
                # The adapter's own sources have local edits: a commit does not name them.
                self.tools_dirty = True
                self.cacheable = False
        self.identities[memo] = identity
        return identity

    # ------------------------------------------------------------------ run set

    def _check_fresh_target(self) -> None:
        """`--fresh` deletes the output directory: only a run set, or an empty or missing directory.
        Being under the results root is not enough (review 2, N5): `$RVW_RESULTS/cache` is there."""
        out = self.out
        if not out.exists() or (out.is_dir() and not any(out.iterdir())):
            return
        if not out.is_dir():
            raise ValueError(f"--fresh: {out} is not a directory")
        rj = out / "run.json"
        try:
            is_run_set = rj.is_file() and json.loads(rj.read_text()).get("schema") == RUN_SET_SCHEMA
        except (OSError, ValueError):
            is_run_set = False
        if not is_run_set:
            raise ValueError(f"--fresh: refusing to delete {out}: it is not a run set (no run.json with schema "
                             f"{RUN_SET_SCHEMA}) and not empty")

    def _check_no_c3_root(self) -> None:
        """A run set never shares its directory with a C3 results.json (review 14): the reader would
        have to choose between the two. A leftover one is refused (not deleted: it may be someone's
        only copy); `--fresh` on a run set removes it with the rest."""
        if self.opts.fresh:
            return
        if (self.out / "results.json").exists():
            raise ValueError(f"{self.out} holds a C3 results.json (an earlier single-suite result): a run set "
                             "cannot be written beside it; use another --out, or remove the file")

    @staticmethod
    def check_plan(plan: list[PlanItem]) -> None:
        """One plan item per suite/config: both write DIR/<suite>/<config> (C3, JUnit, test dirs),
        so a second one overwrote the first one's results (review 11). Merge the rows instead."""
        seen: set[tuple[str, ...]] = set()
        for item in plan:
            item.suite.validate()
            for what, name in (("suite", item.suite.name), ("config", item.config)):
                if not _safe_component(name):
                    raise ConfigError(f"{what} name {name!r} cannot be a directory name of the output "
                                      "(empty, '.', '..', or holds '/', '\\' or NUL)")
            k = path_key(item.suite.name) + path_key(item.config)
            if k in seen:
                raise ConfigError(f"{item.suite.name}/{item.config} is selected more than once (a tier row or "
                                  "--suite/--config repeated, or names differing only in case): both would "
                                  "write the same results; list it once (merge the rows' include patterns)")
            seen.add(k)

    @staticmethod
    def _check_dirs(jobs: list[Job], rdir: Path) -> None:
        """Last check before an adapter starts: one output directory per job (review 13)."""
        seen: dict[tuple[str, ...], Job] = {}
        for j in jobs:
            k = path_key(j.dir.relative_to(rdir).as_posix())
            if k in seen:
                o = seen[k]
                raise ConfigError(f"{o.suite.name}/{o.config}: tests {o.test.id!r} (seed {o.seed}) and "
                                  f"{j.test.id!r} (seed {j.seed}) would share {j.dir}")
            seen[k] = j

    def _discover(self, plan: list[PlanItem]) -> list[list[TestSpec]]:
        """Tests of each plan item. A plan that runs no test (no job) is an error, and so is an
        empty suite unless a --filter made it empty (then other suites of the plan still run)."""
        self.check_plan(plan)
        counts = [seed_count(item, self.opts) for item in plan]
        found = [discover(item.suite, item.include + self.opts.include) for item in plan]
        where = lambda items: ", ".join(f"{i.suite.name}/{i.config}" for i in items)  # noqa: E731
        if not plan or not any(found) or sum(n * len(t) for n, t in zip(counts, found)) == 0:
            filt = f" (filter {', '.join(self.opts.include)})" if self.opts.include else ""
            raise ValueError(f"no tests to run{filt}: {where(plan) or 'empty plan'} matched nothing")
        empty = [i for i, t in zip(plan, found) if not t]
        if empty and not self.opts.include:
            raise ValueError(f"no tests in {where(empty)}: check the suite's dir, glob and include/exclude")
        return found

    def _source_metadata(self) -> dict:
        """The same source identity in standalone C3 files and their run-set manifest."""
        src = {**self.source.to_dict(), "tools_key": self.tools_key, "adapter": self.adapter_id,
               "input_capture": self.start_record, "config_capture": self.core.capture,
               "effective_config": self.config_values}
        if not self.identity_complete:
            uncovered = [self.input_change] if self.input_change else []
            if not self.source_known:
                uncovered.append("core: no source repository and no adapter `identity`")
            src.update(identity_complete=False, identity_uncovered=uncovered)
        return src

    def run(self, plan: list[PlanItem]) -> dict:
        for item in plan:
            self.core.negotiate(item.suite)
        if self.inputs.closed:
            self.__init__(self.core, self.source, self.out, self.opts)
        try:
            with out_lock(self.out) as lk:
                self._out_lock = lk
                try:
                    return self._run(plan)
                finally:
                    self._out_lock = None
        finally:
            self.close()

    def capture_plan(self, plan):
        """Capture discovery, every selected ELF, option inputs and the adapter identity of each
        model before any side of a gate executes."""
        if self._found is not None:
            if repr(plan) != self._captured_plan:
                raise ConfigError("the runner already captured another plan; create a new Runner")
            return self._found
        found = self._discover(plan)
        replay_inputs = {}
        for tests in found:
            for test in tests:
                if test.elf:
                    try:
                        elf = self.inputs.elf(test.elf)
                        replay_inputs[elf.sha256] = elf.size
                    except CaptureError as exc:
                        self._incomplete(str(exc))
        replay_bytes = sum(replay_inputs.values())
        replay_limit = self.opts.replay_max_bytes or self.inputs.capture.max_tree_bytes
        if replay_bytes > replay_limit:
            raise CaptureError('input_not_captured:replay_size',
                               f'selected replay inputs need {replay_bytes} unique bytes; '
                               f'limit is {replay_limit} bytes; raise --replay-max-bytes '
                               f'to at least {replay_bytes}')
        for item in plan:
            options = job_options(item.suite, self.opts)
            try:
                self.inputs.options.identities([options, item.suite.build_options])
            except CaptureError as exc:
                self._incomplete(str(exc))
            if item.suite.kind != "build" or not self.core.identity_capture:
                self._identity(item.config, options)
        self.start_record = self.inputs.record()
        self._found = found
        self._captured_plan = repr(plan)
        return found

    def _run(self, plan: list[PlanItem]) -> dict:
        self.cache_pending, self.suite_jobs = [], []
        self._saved_replays = {}
        run_json = self.out / "run.json"
        if self.opts.fresh:
            self._check_fresh_target()
        self._check_no_c3_root()
        found = self.capture_plan(plan)
        prev = None
        if not self.opts.fresh and (self.out / "current").exists():
            previous = self.opts.previous_generation or open_current(self.out)
            prev = json.loads(previous.read_bytes("run.json"))
            # Resume consumes the previous immutable generation, never a partly rewritten workspace.
            for entry in prev["results"]:
                relative = Path(entry["path"])
                target = self.out / relative
                if target.exists():
                    shutil.rmtree(target)
                for top, dirs, files in os.walk(previous.path / relative):
                    part = Path(top).relative_to(previous.path)
                    (self.out / part).mkdir(parents=True, exist_ok=True)
                    for name in files:
                        (self.out / part / name).write_bytes(previous.read_bytes(part / name))
        elif (self.out / "generations").exists() and not self.opts.fresh:
            raise GenerationError("result generations exist but current is missing; choose a new --out")
        elif run_json.is_file() and not self.opts.fresh:
            # An unpublished (interrupted) run set. This runner holds the output lock.
            prev = json.loads(read_file(run_json))
        if self.opts.fresh and self.out.exists():
            for child in self.out.iterdir():
                if child.name in ("current", "generations"):
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        created = prev["created"] if prev else _iso(_now())
        label = self.opts.label or self.opts.tier or "+".join(dict.fromkeys(p.suite.name for p in plan))
        configs = list(dict.fromkeys(p.config for p in plan))
        run_id = prev["run_id"] if prev else self._new_run_id(created, label, configs)
        self.run_id = run_id
        if not self.cacheable:
            why = ("the core source is unknown (no source_repo or --source, no adapter `identity`)"
                   if not self.source_known
                   else self.input_change if self.input_change
                   else "core source is dirty or has no revision" if (self.source.dirty or not self.source.rev)
                   else "the adapter's own sources are dirty (identity source.tools_dirty)")
            _say(self.opts, f"rvw: source-based cache off ({why}); complete RTL identities can still reuse results"
                 + ("" if self.identity_complete else "; no resume either"))
        summary = {
            "schema": RUN_SET_SCHEMA, "run_id": run_id, "core": self.core.name,
            "core_config": str(self.core.path), "tier": self.opts.tier, "label": label,
            "created": created, "finished": None,
            "source": self._source_metadata(),
            "seeds": {"mode": "random" if self.opts.random_seeds else "fixed", "base": self.opts.seed_base},
            "results": [],
        }
        self.out.mkdir(parents=True, exist_ok=True)
        write_json(run_json, summary)
        for item, tests in zip(plan, found):
            res = self.run_suite(item, tests)
            rel = res.path.relative_to(self.out).as_posix()
            summary["results"].append({"suite": res.suite, "config": res.config, "path": rel,
                                       "counts": res.counts(), "tests": len(res.tests),
                                       "inconclusive": sum(not t.conclusive for t in res.tests)})
            write_json(run_json, summary)
        if not self._check_inputs():
            self.cache_pending.clear()
            for jobs, res, rdir in self.suite_jobs:
                self._distrust(jobs)
                res.tests = [self._entry(job, False) for job in jobs]
                save_results(res, rdir)
                write_junit(res, rdir / "junit.xml")
            for entry, (_, res, _) in zip(summary["results"], self.suite_jobs):
                entry["counts"] = res.counts()
                entry["inconclusive"] = sum(not t.conclusive for t in res.tests)
        total: dict[str, int] = {}
        for r in summary["results"]:
            for k, v in r["counts"].items():
                total[k] = total.get(k, 0) + v
        summary["counts"] = total
        # `counts` is by status; an inconclusive result (any status) is not a pass either.
        summary["inconclusive"] = sum(r["inconclusive"] for r in summary["results"])
        # No test at all is never a success (review 11), whatever let the plan through.
        summary["ok"] = bool(total) and set(total) <= {"pass"} and summary["inconclusive"] == 0
        summary["finished"] = _iso(_now())
        write_json(run_json, summary)
        def build_generation(directory):
            # Copy regular artifacts only after all adapters have stopped. Never hardlink mutable jobs.
            for entry in summary["results"]:
                shutil.copytree(self.out / entry["path"], directory / entry["path"])
            for saved in self._saved_replays.values():
                target = directory / saved.relative_to(self.out)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(saved, target)
            # Replays in immutable generations point at that generation's saved ELF.
            final = directory.with_name(directory.name.removeprefix('.building-'))
            for entry in summary['results']:
                for result in (directory / entry['path']).rglob('result.json'):
                    data = json.loads(result.read_text())
                    if isinstance(data.get('replay'), str):
                        saved = self._saved_replays.get(data.get('elf_sha256'))
                        if saved is not None:
                            relative = saved.relative_to(self.out)
                            data['replay'] = data['replay'].replace(
                                shlex.quote(str(saved)), shlex.quote(str(final / relative)))
                        write_json(result, data)
            write_json(directory / "run.json", summary)
            write_json(directory / "capture.json", {"capture": self.inputs.record(),
                       "adapter_identities": self.identities})
        generation = publish(self.out, build_generation)
        summary["generation"] = generation
        if self.cache:
            for job in self.cache_pending:
                self.cache.put(job.key, job.dir)
        if self.opts.index:
            append_index({"run_id": run_id, "path": str(self.out), "created": created,
                          "finished": summary["finished"], "core": self.core.name,
                          "core_rev": self.source.short, "core_rev_full": self.source.rev,
                          "core_dirty": self.source.dirty, "tier": self.opts.tier, "label": label,
                          "suites": list(dict.fromkeys(p.suite.name for p in plan)), "configs": configs,
                          "counts": total, "inconclusive": summary["inconclusive"], "ok": summary["ok"]},
                         self.opts.results_root)
        return summary

    def preview(self, plan: list[PlanItem]) -> dict:
        try:
            return self._preview(plan)
        finally:
            self.close()

    def _preview(self, plan: list[PlanItem]) -> dict:
        """What `run` would do, without simulating: per suite/config, tests already finished in the
        output dir, available from the cache, and left to run."""
        self.run_id = "preview"
        self._check_no_c3_root()
        self.check_plan(plan)
        previous = self.opts.previous_generation
        if previous is None and (self.out / "current").exists():
            previous = open_current(self.out)
        if previous is not None:
            self.opts.previous_generation = previous
            self.run_id = json.loads(previous.read_bytes("run.json"))["run_id"]
        elif not self.opts.random_seeds and (self.out / "run.json").is_file():
            self.run_id = json.loads(read_file(self.out / "run.json"))["run_id"]
        found = self.capture_plan(plan)
        rows = []
        cacheable = False
        for item, tests in zip(plan, found):
            rdir = self.out / item.suite.name / item.config
            jobs = self._jobs(item, tests, rdir)
            cacheable = cacheable or any(j.key for j in jobs)
            finished = [self._finished(j) for j in jobs]
            done = sum(finished)
            cached = sum(1 for j, f in zip(jobs, finished)
                         if not f and self.cache and j.key and self._cache_usable(j))
            rows.append({"suite": item.suite.name, "config": item.config, "jobs": len(jobs), "done": done,
                         "cached": cached, "to_run": len(jobs) - done - cached})
        return {"schema": "rvw.regress-plan/1", "core": self.core.name, "out": str(self.out),
                "source": self.source.to_dict(), "cacheable": bool(cacheable),
                "identity_complete": self.identity_complete, "plan": rows,
                "to_run": sum(r["to_run"] for r in rows)}

    def _new_run_id(self, created: str, label: str, configs: list[str]) -> str:
        rev = (self.source.short or "norev") + ("-dirty" if self.source.dirty else "")
        # A random suffix: two runs started in the same second must not share an id (review 10);
        # the index only lists finished runs, so it cannot catch a concurrent one.
        base = (f"{created.replace(':', '-')}-{self.core.name}-{label}-{'+'.join(configs)}-{rev}"
                f"-{os.urandom(3).hex()}")
        taken = {e.get("run_id") for e in read_index(self.opts.results_root) if e.get("path") != str(self.out)}
        run_id, n = base, 1
        while run_id in taken:
            n += 1
            run_id = f"{base}-{n}"
        return run_id

    # ------------------------------------------------------------------ one suite on one config

    def _check_inputs(self) -> bool:
        """Verify the recorded tools once, before the run set is published."""
        try:
            self.inputs.capture.verify_tools()
        except (CaptureError, OSError) as exc:
            self._incomplete(str(exc))
        if self.input_change:
            _say(self.opts, f"rvw: {self.input_change}")
        return self.input_change is None

    def _distrust(self, jobs: list[Job], *, not_run: bool = False) -> None:
        """Mark C1 as well as C3 unusable; neither direct readers nor resume may trust it."""
        for j in jobs:
            j.key = None
            try:
                if not_run:
                    raise FileNotFoundError
                r = load_run(j.dir)
            except (OSError, ValueError, SchemaError):
                self._synth(j, "error", self.input_change)
                r = load_run(j.dir)
            r.extra["inconclusive"] = self.input_change
            save_run(r, j.dir)
            self._write_job(j, cached=False)

    def run_suite(self, item: PlanItem, tests: list[TestSpec]) -> SuiteResults:
        suite, config = item.suite, item.config
        self.core.negotiate(suite)
        rdir = self.out / suite.name / config
        rdir.mkdir(parents=True, exist_ok=True)
        jobs = self._jobs(item, tests, rdir)
        self._check_dirs(jobs, rdir)
        # Cache hits and resume need this check too. Keep validation, adapter execution and
        # publication in one lock hold; a lock wait must never separate identity from execution.
        with locks.held(self.core.lock, self.core.lock_dir, log=self.opts.log):
            return self._run_suite(item, jobs, rdir)

    def _run_suite(self, item: PlanItem, jobs: list[Job], rdir: Path) -> SuiteResults:
        suite, config = item.suite, item.config
        valid = self.input_change is None
        if not valid:
            _say(self.opts, f"rvw: {self.input_change}")
        done, cached, pending = [], [], []
        for j in jobs:
            if not valid:
                pending.append(j)
            elif self._finished(j):
                done.append(j)
            elif self.cache and j.key and self._cache_usable(j) and self.cache.restore(j.key, j.dir):
                self._write_job(j, cached=True)
                cached.append(j)
            else:
                pending.append(j)
        _say(self.opts, f"rvw: {suite.name}/{config}: {len(jobs)} tests, {len(done)} already done, "
                        f"{len(cached)} from cache, {len(pending)} to run")
        if pending and valid:
            if suite.kind == "build":
                for j in pending:
                    self._run_build(j, rdir)
            else:
                self._run_tests(pending, rdir, suite, config)
        if not valid:
            self._distrust(jobs, not_run=True)
            cached = []
        else:
            for j in pending:
                self._write_job(j, cached=False)
        cached_ids, pending_ids = {id(j) for j in cached}, {id(j) for j in pending}
        entries = [self._entry(j, id(j) in cached_ids) for j in jobs]
        if self.cache:
            for j, e in zip(jobs, entries):
                if (j.key and id(j) in pending_ids and e.conclusive
                        and (e.status == "pass" or j.params.get("rtl_identity"))):
                    self.cache_pending.append(j)
        src = self._source_metadata()
        extra = {"run_set": os.path.relpath(self.out, rdir),
                 "seeds": {"mode": "random" if self.opts.random_seeds else "fixed", "base": self.opts.seed_base}}
        if self.opts.include:
            extra["filter"] = list(self.opts.include)
        extra["perf_metrics"] = list(suite.perf_metrics)
        extra["option_inputs"] = jobs[0].params["option_inputs"] if jobs else {}
        extra["metric_keys"] = {"cycles": suite.cycles_key, "instret": suite.instret_key}
        res = SuiteResults(run_id=self.run_id, suite=suite.name, core=self.core.name, config=config,
                           created=_iso(_now()), source=src, tests=entries, extra=extra)
        save_results(res, rdir)
        write_junit(res, rdir / "junit.xml")
        c = res.counts()
        n_inc = sum(not t.conclusive for t in res.tests)
        _say(self.opts, f"rvw: {suite.name}/{config}: " + (", ".join(f"{v} {k}" for k, v in c.items())
                                                         or "no tests (the filter matched none)")
             + (f" ({n_inc} inconclusive)" if n_inc else ""))
        self.suite_jobs.append((jobs, res, rdir))
        return res

    def _jobs(self, item: PlanItem, tests: list[TestSpec], rdir: Path) -> list[Job]:
        suite = item.suite
        suite.validate()
        n = seed_count(item, self.opts)
        options = job_options(suite, self.opts)
        jobs = []
        for t in tests:
            seeds = [0] if suite.kind == "build" else _seeds(n, self.opts, self.run_id, f"{suite.name}/{item.config}/{t.id}")
            if t.elf:
                try:
                    elf_sha = self.inputs.elf(t.elf).sha256
                except CaptureError as exc:
                    self._incomplete(str(exc))
                    elf_sha = None
            else:
                elf_sha = None
            try:
                option_inputs = self.inputs.options.identities([options, suite.build_options])
            except CaptureError as exc:
                self._incomplete(str(exc))
                option_inputs = None
            identity = (self._identity(item.config, options)
                        if suite.kind != "build" or not self.core.identity_capture else None)
            document = identity and identity["document"]
            claims = document["result_claims"] if document else {}
            rtl_identity = _rtl_identity(document)
            for s in seeds:
                d = rdir / "tests" / t.id
                if len(seeds) > 1:
                    d = d / f"seed-{s}"
                # Everything that determines the result. Resume compares it as is (so a second
                # edit of a dirty tree, another adapter or toolchain reruns); the cache hashes it.
                params = {"runner_identity_version": JOB_IDENTITY_VERSION,
                          "core": self.core.name, "core_rev": self.source.rev, "core_dirty": self.source.dirty,
                          "core_fingerprint": self.source.fingerprint, "core_links": self.source.links,
                          "config": item.config, "kind": suite.kind, "elf_sha256": elf_sha,
                          "test": t.id, "elf": str(t.elf) if t.elf else None,
                          "execution": {"cwd": str(self.inputs.cwd), "jobs": self.jobs,
                                        "timeout_s": self.opts.timeout_s or suite.timeout_s,
                                        "startup_s": self.startup_s, "wall_timeout": self.core.wall_timeout,
                                        "build_first": self.core.build_first,
                                        "build_timeout_s": self.core.build_timeout_s},
                          "seed": s if suite.kind != "build" else None, "options": options,
                          "build_options": list(suite.build_options) if suite.kind == "build" else None,
                          "option_inputs": option_inputs,
                          "tools": self.tools_key, "adapter": self.adapter_id,
                          "identity": identity["sha256"] if identity else None}
                if rtl_identity:
                    for field in ("core_rev", "core_dirty", "core_fingerprint", "core_links"):
                        params.pop(field)
                    params["rtl_identity"] = True
                if self.nonce:
                    params["nonce"] = self.nonce
                key = None
                if (self.cacheable or (rtl_identity and not self.tools_dirty)) and suite.kind != "build":
                    key = _cache_key(self.inputs.capture, {"params": params, "config": self.core.capture,
                                                         "effective_config": self.config_values},
                                                        complete=self.identity_complete)
                jobs.append(Job(suite, item.config, t, s, d, (d / "result.json").relative_to(rdir).as_posix(),
                                options, params, key, len(seeds) > 1, claims))
        return jobs

    def _job_error(self, j: Job, r: RunResult) -> str | None:
        """Adapter evidence must describe the requested job, including all requested options."""
        if j.suite.kind == "build":
            conflict = self._build_identity_error(r.extra.get("build"), j.config)
            if conflict:
                return conflict
        expected = {"core": self.core.name, "config": j.config,
                    "elf_sha256": j.params["elf_sha256"], "seed": j.params["seed"]}
        for key, wanted in expected.items():
            if getattr(r, key) != wanted:
                return f"C1 job identity {key} {getattr(r, key)!r} differs from requested {wanted!r}"
        if j.test.elf:
            # Fresh results name the captured copy that ran; published ones its source path.
            elf = self.inputs.elf(j.test.elf)
            if r.elf not in (str(elf.copy), elf.source):
                return f"C1 elf {r.elf!r} is not the captured input of this job"
        actual = r.to_dict()
        from .adapter_capture import claim_error
        conflict = claim_error(j.claims, actual)
        if conflict:
            return conflict
        recorded = actual.get("options", {})
        if not isinstance(recorded, dict):
            return "C1 job identity options must be an object"
        recorded = {key.removeprefix("--").replace("-", "_"): value for key, value in recorded.items()}
        for key, wanted in j.options.items():
            values = [mapping[key] for mapping in (actual, recorded) if key in mapping]
            if key == "rvfi_trace" and wanted is True and not values and isinstance(r.replay, str):
                # Existing C1 adapters record this observation flag in replay and artifacts.
                # Require both, and bind the artifact to this result directory (also in cache).
                try:
                    argv = shlex.split(r.replay)
                except ValueError:
                    argv = []
                flags = [arg for arg in argv if arg == "--rvfi-trace" or arg.startswith("--rvfi-trace=")]
                if flags == ["--rvfi-trace"]:
                    pos = argv.index("--rvfi-trace")
                    if pos + 1 < len(argv) and not argv[pos + 1].startswith("--"):
                        flags = []  # a value after a boolean flag is not a valid C1 replay
                artifact = r.artifacts.get("rvfi_trace")
                root = r.dir or j.dir
                if flags == ["--rvfi-trace"] and isinstance(artifact, str):
                    trace = (root / artifact).resolve()
                    if trace.is_relative_to(root.resolve()) and trace.is_file():
                        values.append(True)
            if not values or any(json.dumps(v, sort_keys=True) != json.dumps(wanted, sort_keys=True)
                                 for v in values):
                return f"C1 job identity option {key} is missing or differs from requested {wanted!r}"
        return None

    def _provenance_error(self, r: RunResult) -> str | None:
        """C1 must agree with the source that was selected, before resume, cache or C3 publication."""
        if self.source.path is None:
            return None
        actual = r.source
        expected = self.source.to_dict()
        repo = actual.get("core_repo")
        if repo != expected["core_repo"]:
            return f"C1 source.core_repo {repo!r} conflicts with selected source {str(self.source.path)!r}"
        rev = self.source.rev
        if rev and not any(actual.get(k) for k in ("core_rev", "core_rev_full")):
            return "C1 source has no revision for the selected source"
        for key in ("core_rev", "core_rev_full"):
            value = actual.get(key)
            if value is None:
                continue
            matches = (value == rev if key == "core_rev_full" else
                       isinstance(value, str) and rev is not None and 7 <= len(value) <= len(rev)
                       and rev.startswith(value))
            if not matches:
                return f"C1 source.{key} {value!r} conflicts with selected revision {rev!r}"
        for key in ("core_dirty", "core_fingerprint", "core_links", "core_identity_covered"):
            if key not in actual:
                continue
            wanted = expected.get(key, True if key == "core_identity_covered" else None)
            if actual[key] != wanted or (key in ("core_dirty", "core_identity_covered")
                                        and not isinstance(actual[key], bool)):
                return f"C1 source.{key} {actual[key]!r} conflicts with selected source {wanted!r}"
        return None

    def _finished(self, j: Job) -> bool:
        """Resume: a test whose directory already holds a usable result for the same job."""
        jf, rf = j.dir / JOB_FILE, j.dir / "result.json"
        if not (jf.is_file() and rf.is_file()):
            return False
        try:
            previous = self.opts.previous_generation
            if previous is not None:
                meta = json.loads(previous.read_bytes(jf.relative_to(self.out)))
                r = RunResult.from_dict(json.loads(previous.read_bytes(rf.relative_to(self.out))))
            else:
                meta = json.loads(read_file(jf))
                r = load_run(rf)
        except (OSError, ValueError, SchemaError):
            return False
        return (meta.get("params") == j.params and r.why_inconclusive is None
                and self._provenance_error(r) is None and self._job_error(j, r) is None)

    def _cache_usable(self, j: Job) -> bool:
        """Reuse conclusive passes, or conclusive failures with complete RTL identity.

        The failure status stays unchanged. Incomplete results always run again.
        """
        p = self.cache.get(j.key) if self.cache else None
        if p is None:
            return False
        try:
            r = self.cache.load(j.key)
            return ((r.status == "pass" or j.params.get("rtl_identity")) and r.why_inconclusive is None
                    and (j.params.get("rtl_identity") or self._provenance_error(r) is None)
                    and self._job_error(j, r) is None)
        except (OSError, ValueError, SchemaError):
            return False

    def _write_job(self, j: Job, cached: bool) -> None:
        if (j.dir / "result.json").is_file():
            write_json(j.dir / JOB_FILE, {"params": j.params, "key": j.key, "cached": cached,
                                          "elf": str(j.test.elf) if j.test.elf else None})

    # ------------------------------------------------------------------ adapter calls

    def _proc(self, cmd: list[str], log_path: Path, timeout: float, stdout_path: Path | None = None,
              watchdog=None) -> tuple[int | None, bool, float]:
        """Run `cmd` in its own process group. Returns (exit code, timed out, seconds). `watchdog()`
        is called every 2 s; a string it returns stops the whole group, as a timeout does."""
        finite_number(timeout, "adapter timeout", positive=True)
        t0 = time.monotonic()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log:
            log.write(f"$ {shlex.join(cmd)}\n".encode())
            log.flush()
            out = open(stdout_path, "wb") if stdout_path else log
            lk = self._out_lock
            record = lk.reserve() if lk is not None else None
            # run_group carries the output ownership descriptor on stderr. The stdlib-only
            # launcher preserves it, registers its process group, redirects stderr, then execs.
            # This also closes the Popen/cancellation setup window through shared proc cleanup.
            launcher = """import os, pathlib, sys
fd = os.dup(2)
os.set_inheritable(fd, True)
log, record, *command = sys.argv[1:]
with open(log, 'ab') as stream:
    os.dup2(stream.fileno(), 2)
if record:
    path = pathlib.Path(record)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(str(os.getpid()) + '\\n')
    os.replace(temporary, path)
os.execvpe(command[0], command, os.environ)
"""
            stop, expired = threading.Event(), threading.Event()
            reason = []

            def watch():
                while not stop.wait(2):
                    why = watchdog() if watchdog else None
                    if not why:
                        continue
                    reason.append(why)
                    expired.set()
                    if record is not None:
                        try:
                            pgid = int(record.read_text().strip())
                            os.killpg(pgid, signal.SIGTERM)
                            if not stop.wait(5):
                                os.killpg(pgid, signal.SIGKILL)
                        except (OSError, ValueError):
                            pass
                    return

            watcher = threading.Thread(target=watch, daemon=True) if watchdog and record is not None else None
            if watcher:
                watcher.start()
            try:
                result = run_group([sys.executable, '-c', launcher, str(log_path),
                                    str(record) if record else '', *cmd],
                                   stdout=out, stderr=lk.fd if lk is not None else log,
                                   cwd=self.inputs.cwd, env=self.env, timeout=timeout)
                timed_out = result.timed_out or expired.is_set()
                if timed_out:
                    log.write(f"\nrvw: killed: {reason[0] if reason else f'{timeout:.0f}s wall-clock timeout'}\n".encode())
                return (None if timed_out else result.returncode), timed_out, time.monotonic() - t0
            except OSError as exc:
                log.write(f"rvw: cannot start: {exc}\n".encode())
                return 127, False, time.monotonic() - t0
            finally:
                stop.set()
                if watcher:
                    watcher.join()
                if stdout_path:
                    out.close()
                if lk is not None:
                    lk.prune()

    def _synth(self, j: Job, status: str, message: str, wall_s: float | None = None, artifacts=None,
               replay=None) -> None:
        """Writes a result for a job the adapter gave none for (or a build suite's outcome). Such a
        result is `synthesized`: never cached or resumed, and inconclusive in a comparison."""
        extra = {"options": dict(j.options)}
        if status in ("error", "timeout"):
            extra["synthesized"] = True
        if status == "timeout":
            extra["wall_clock_timeout"] = True
        r = RunResult(status=status, core=self.core.name, config=j.config,
                      elf=self.inputs.elf(j.test.elf).source if j.test.elf else "",
                      elf_sha256=j.params["elf_sha256"], seed=j.seed if j.test.elf else None,
                      max_cycles=j.options.get("max_cycles"), mem_latency=j.options.get("mem_latency"),
                      message=message, wall_s=round(wall_s, 3) if wall_s is not None else None,
                      source={**self.source.to_dict(), "tools_rev": None},
                      artifacts=artifacts or {}, replay=replay, extra=extra)
        j.dir.mkdir(parents=True, exist_ok=True)
        save_run(r, j.dir)

    def _build_identity_error(self, build, config: str) -> str | None:
        """Check identity when reported, including RiscvSim's rvw.build/1 models."""
        if not isinstance(build, dict):
            return None  # C1 also permits adapters that report only their exit status.
        if "core" in build and build["core"] != self.core.name:
            return f"build identity core {build['core']!r} differs from requested {self.core.name!r}"
        configs = [build["config"]] if "config" in build else []
        if "models" in build:
            models = build["models"]
            if not isinstance(models, list) or not models:
                return "build identity models must be a non-empty list"
            for entry in models:
                model = entry.get("model") if isinstance(entry, dict) else None
                if not isinstance(model, dict) or "config" not in model:
                    return "build identity model has no config"
                configs.append(model["config"])
        if any(actual != config for actual in configs):
            return f"build identity configs {configs!r} differ from requested {config!r}"
        return None

    def _run_build(self, j: Job, rdir: Path) -> None:
        shutil.rmtree(j.dir, ignore_errors=True)
        j.dir.mkdir(parents=True)
        cmd = [*self.adapter, "build", "--config", j.config, *j.suite.build_options, "--json"]
        if self.opts.rvfi_trace:
            cmd.append("--rvfi")
        timeout = self.opts.timeout_s or j.suite.timeout_s
        _say(self.opts, f"rvw: {j.suite.name}/{j.config}: {shlex.join(cmd)}")
        rc, timed_out, wall = self._proc(cmd, j.dir / "build.log", timeout, stdout_path=j.dir / "build.out")
        out = (j.dir / "build.out").read_text(errors="replace")
        extra = None
        try:
            extra = json.loads(out) if out.strip() else None
        except json.JSONDecodeError:
            pass
        if timed_out:
            status, msg = "timeout", f"build wall-clock timeout after {timeout:.0f}s"
        elif rc == 0:
            msg = self._build_identity_error(extra, j.config)
            status = "error" if msg else "pass"
        else:
            status, msg = "error", f"build failed (exit {rc}): {_tail(j.dir / 'build.log', out)}"
        self._synth(j, status, msg, wall, artifacts={"log": "build.log", "stdout": "build.out"},
                    replay=shlex.join(cmd))
        if extra is not None:
            r = load_run(j.dir)
            r.extra["build"] = extra
            save_run(r, j.dir)

    def _run_tests(self, pending: list[Job], rdir: Path, suite: Suite, config: str) -> None:
        log = rdir / "adapter.log"
        for j in pending:
            shutil.rmtree(j.dir, ignore_errors=True)
            j.dir.mkdir(parents=True)
        per_test = self.opts.timeout_s or suite.timeout_s
        timeout = finite_number(self.startup_s + per_test * math.ceil(len(pending) / self.jobs),
                                "batch timeout", positive=True)
        finite_number(per_test + watchdog_margin(per_test) + self.startup_s,
                      "watchdog timeout", positive=True)
        if self.core.build_first and not self.core.persistent:
            cmd = [*self.adapter, "build", "--config", config]
            if self.opts.rvfi_trace:
                cmd.append("--rvfi")
            _say(self.opts, f"rvw: {suite.name}/{config}: building")
            rc, timed_out, _ = self._proc(cmd, log, self.core.build_timeout_s)
            if rc != 0:
                why = "timed out" if timed_out else f"exit {rc}"
                msg = f"build failed ({why}): {_tail(log)}"
                for j in pending:
                    self._synth(j, "error", msg, artifacts={})
                return
        if self.core.persistent and self.jobs > 1:
            from rvw.sim.persistent import run_workers
            # Capture before starting threads. Each worker owns a separate JVM,
            # manifest, watchdog and process group.
            for j in pending:
                self.inputs.elf(j.test.elf)

            worker_locks = locks.thread_context()

            def worker(number, batch, cancel):
                directory = rdir / f"worker-{number}"
                directory.mkdir(exist_ok=True)
                budget = self.startup_s + per_test * len(batch)
                with worker_locks():
                    return self._run_many(batch, directory, config, budget, "all", cancel=cancel)

            results = run_workers(pending, self.jobs, worker)
            rc = next((code for code, _ in results if code != 0), 0)
            timed_out = any(expired for _, expired in results)
            log.write_text("Persistent worker logs:\n" + "".join(
                f"worker-{n}/adapter.log\n" for n in range(len(results))))
        else:
            rc, timed_out = self._run_many(pending, rdir, config, timeout, "all")
        missing = [j for j in pending if not (j.dir / "result.json").is_file()]
        if missing and (timed_out or len(missing) < len(pending)):
            # Isolate the test that hung or crashed the batch: rerun the rest one by one.
            _say(self.opts, f"rvw: {suite.name}/{config}: {len(missing)} without a result after the batch "
                            f"({'timeout' if timed_out else f'exit {rc}'}); rerunning them one at a time")
            for j in missing:
                rc1, t1 = self._run_many([j], rdir, config, self.startup_s + per_test, j.test.id)
                if not (j.dir / "result.json").is_file():
                    if t1:
                        self._synth(j, "timeout", f"wall-clock timeout after {per_test:.0f}s (rvw regress)")
                    else:
                        self._synth(j, "error", f"adapter wrote no result.json (exit {rc1}): {_tail(log)}")
        elif missing:
            msg = f"adapter wrote no results (exit {rc}): {_tail(log)}"
            for j in missing:
                self._synth(j, "error", msg)

    def _run_many(self, jobs: list[Job], rdir: Path, config: str, timeout: float, tag: str, cancel=None):
        """One `run-many` call. Besides the batch budget `timeout`, a watchdog stops the batch when no
        new result.json appears for `timeout_s` (+ margin) after the first `startup_s`: a hung test
        then costs about one test timeout, not the whole batch budget."""
        manifest = rdir / ("manifest.jsonl" if tag == "all" else f"manifest-retry.jsonl")
        per_test = self.opts.timeout_s or jobs[0].suite.timeout_s
        with open(manifest, "w") as f:
            for j in jobs:
                line = {**j.options, "elf": str(self.inputs.elf(j.test.elf).copy), "out": str(j.dir),
                        "config": config, "seed": j.seed}
                if self.core.wall_timeout:
                    line["wall_timeout"] = per_test
                f.write(json.dumps(line) + "\n")
        cmd = [*self.adapter, "run-many", "--manifest", str(manifest), "--jobs", str(1 if self.core.persistent else min(self.jobs, len(jobs)))]
        if self.core.persistent:
            cmd.append("--persistent")
        margin = watchdog_margin(per_test)
        t0 = time.monotonic()
        state = {"n": 0, "progress": t0}

        def watchdog():
            if cancel is not None and cancel.is_set():
                return "persistent worker pool cancelled"
            n = sum((j.dir / "result.json").is_file() for j in jobs)
            now = time.monotonic()
            if n != state["n"]:
                state["n"], state["progress"] = n, now
                if len(jobs) > 1:
                    _say(self.opts, f"rvw: {jobs[0].suite.name}/{config}: {n}/{len(jobs)} done")
            limit = per_test + margin + (self.startup_s if n == 0 else 0)
            if n < len(jobs) and now - state["progress"] > limit:
                return f"no new result for {now - state['progress']:.0f}s ({n}/{len(jobs)} done)"
            return None

        rc, timed_out, _ = self._proc(cmd, rdir / "adapter.log", timeout, watchdog=watchdog)
        return rc, timed_out

    # ------------------------------------------------------------------ C3 entries

    def _entry(self, j: Job, cached: bool) -> TestEntry:
        rf = j.dir / "result.json"
        try:
            raw = json.loads(rf.read_text())
            r = RunResult.from_dict(raw)
        except (OSError, ValueError) as e:
            self._synth(j, "error", f"unreadable result.json: {e}")
            raw = json.loads(rf.read_text())
            r = RunResult.from_dict(raw)
        conflict = (None if cached and j.params.get("rtl_identity") else self._provenance_error(r)) or self._job_error(j, r)
        if conflict:
            r.extra["inconclusive"] = conflict
            j.key = None
            save_run(r, j.dir)
            self._write_job(j, cached=False)
            cached = False
        if not conflict:
            if cached and j.params.get("rtl_identity"):
                r.extra["reused_from_source"] = r.extra.get("reused_from_source", r.source)
            if isinstance(r.extra.get('options'), dict):
                r.extra['options'].update(j.options)
            for key, value in j.options.items():
                if key in r.extra:
                    r.extra[key] = value
            r.source = {**r.source, **self._source_metadata()}
            r.extra["input_capture"] = {"elf_sha256": j.params["elf_sha256"], "inputs_key": self.tools_key}
            if j.test.elf:
                elf = self.inputs.elf(j.test.elf)
                r.elf = elf.source
                if r.replay:
                    saved = self.out / 'replay-inputs' / f'{elf.sha256}.elf'
                    if elf.sha256 not in self._saved_replays:
                        saved.parent.mkdir(parents=True, exist_ok=True)
                        saved.unlink(missing_ok=True)
                        shutil.copyfile(elf.copy, saved)
                        self._saved_replays[elf.sha256] = saved
                    # Remove the previous per-job layout when resuming an older run.
                    if r.artifacts.get('replay_elf') == 'replay.elf':
                        (j.dir / 'replay.elf').unlink(missing_ok=True)
                    r.artifacts['replay_elf'] = os.path.relpath(saved, j.dir)
                    try:
                        argv = shlex.split(r.replay)
                        previous_elf = argv[argv.index('--elf') + 1]
                    except (ValueError, IndexError):
                        previous_elf = str(elf.copy)
                    r.replay = r.replay.replace(shlex.quote(previous_elf), shlex.quote(str(saved)))
            save_run(r, j.dir)
        cycles, cycles_origin = _lookup_origin(raw, j.suite.cycles_key)
        instret, instret_origin = _lookup_origin(raw, j.suite.instret_key)
        metrics = dict(r.metrics)
        origins = {name: f"metrics.{name}" for name in metrics}
        origins.update(cycles=cycles_origin, instret=instret_origin, wall_s="wall_s")
        if (isinstance(cycles, int) and not isinstance(cycles, bool)
                and isinstance(instret, int) and not isinstance(instret, bool) and cycles > 0
                and "ipc" not in metrics):
            metrics["ipc"] = instret / cycles
            origins["ipc"] = {"operation": "instret/cycles", "instret": instret_origin,
                              "cycles": cycles_origin}
        extra = {"metric_origins": origins}
        if isinstance(raw.get("rtl_sha256"), str):
            extra["rtl_sha256"] = raw["rtl_sha256"]
        if j.params["identity"] is not None:
            extra["adapter_identity"] = j.params["identity"]
        if r.status != "pass":
            if r.message:
                # Compare rebuilds failure identity from this evidence. Do not truncate it.
                extra["message"] = r.message
                extra["message_complete"] = True
            if r.fail_code is not None:
                extra["fail_code"] = r.fail_code
        if r.status == "rvfi_error" and "rvfi_errcode" in r.details:
            extra["details"] = {"rvfi_errcode": r.details["rvfi_errcode"]}
        if r.extra.get("synthesized"):
            extra["synthesized"] = True
        if r.extra.get("wall_clock_timeout"):
            # Whatever the status (review 13: a pass with `wall_clock_timeout` became conclusive).
            extra["wall_clock_timeout"] = True
        why = r.why_inconclusive
        if why:
            # The complete shared rule (`RunResult.why_inconclusive`: the C1 mark, attribution,
            # harness error, synthesized, wall-clock timeout), whatever the status: an
            # inconclusive pass is no pass (reviews 10, 13). The C3 entry carries the reason, so
            # `TestEntry.conclusive` (compare, cache, JUnit, run.json) agrees with resume.
            extra["inconclusive"] = why[:MESSAGE_MAX]
        if cached:
            extra["cached"] = True
        if j.multi_seed:
            extra["multi_seed"] = True
        if j.test.elf:
            extra["elf"] = str(j.test.elf)
        actual_options = r.extra.get("options")
        actual_options = actual_options if isinstance(actual_options, dict) else {}
        extra.update(elf_sha256=j.params["elf_sha256"],
                     options={**actual_options, **j.options,
                              "max_cycles": r.max_cycles, "mem_latency": r.mem_latency},
                     kind=j.suite.kind)
        if j.suite.kind == "build":
            extra["build_options"] = list(j.params['build_options'])
        return TestEntry(id=j.test.id, status=r.status, seed=r.seed if r.seed is not None else (j.seed if j.test.elf else None),
                         cycles=cycles if isinstance(cycles, int) else None,
                         instret=instret if isinstance(instret, int) else None,
                         wall_s=r.wall_s, run=j.rel, signature=run_signature(r), metrics=metrics, extra=extra)


def _group_alive(pgid: int) -> bool:
    """True while some process of group `pgid` exists (EPERM: it exists, or is exiting: alive)."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class OutLock:
    """An output lock and one durable ownership record per adapter launch."""

    def __init__(self, f, writers: Path):
        self.file, self.writers = f, writers
        writers.mkdir(exist_ok=True)

    @property
    def fd(self) -> int:
        return self.file.fileno()

    def reserve(self) -> Path:
        # An empty record is deliberately unresolved. If rvw dies before storing the pgid, the
        # next caller must refuse instead of assuming no adapter was started.
        record = self.writers / (os.urandom(16).hex() + ".writer")
        with record.open("x"):
            pass
        return record

    def prune(self) -> list[str]:
        """Remove only known-empty groups. Unknown or unreadable records block reuse too."""
        live = []
        for record in self.writers.glob("*.writer"):
            try:
                value = record.read_text().strip()
            except OSError:
                value = ""
            if not value.isdigit() or int(value) <= 1:
                live.append(f"unresolved launch {record}")
            elif _group_alive(int(value)):
                live.append(f"process group {value}")
            else:
                record.unlink(missing_ok=True)
        return live


@contextlib.contextmanager
def out_lock(out: Path):
    """Exclusive output ownership, including adapters left alive by a killed runner.

    The flock is outside --out (which --fresh deletes) and is passed to each adapter. Durable
    launch records also cover adapters that close inherited fds. A reservation precedes Popen,
    so interruption before pid registration fails closed. Only known-empty groups are pruned.
    """
    real = Path(os.path.realpath(out))
    d = lock_dir() / "out"
    d.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(str(real).encode()).hexdigest()[:32]
    f = open(d / (name + ".lock"), "a+")
    try:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError(f"{real} is in use by another rvw regress run or its adapter; "
                             "wait for it or choose another --out") from None
        lk = OutLock(f, d / (name + ".writers"))
        live = lk.prune()
        if live:
            raise ValueError(f"{real} is in use by an earlier rvw regress run: {'; '.join(live)}. "
                             "Choose another --out, or stop all adapters of that run before removing "
                             f"unresolved records from {lk.writers}")
        f.seek(0)
        f.truncate()
        f.write(f"{os.getpid()} {real}\n")
        f.flush()
        yield lk
    finally:
        # Do not explicitly LOCK_UN: children share this file description and may still need it.
        f.close()


def _safe_component(name: str) -> bool:
    return isinstance(name, str) and name not in ("", ".", "..") and not any(c in name for c in "/\\\0")


def watchdog_margin(per_test: float) -> float:
    """How long past `timeout_s` the batch watchdog waits for a new result. Longer than the time an
    adapter takes to end a run at its wall-clock limit (C1: within max(2 s, 10%); RiscvSim abandons
    a stuck run then), plus the 2 s poll, so rvw does not stop a batch the adapter is about to
    unblock (review 2, N6)."""
    finite_number(per_test, "watchdog per_test timeout", positive=True)
    return 10.0 + 0.2 * per_test


def _tail(path: Path, extra: str = "", n: int = 3) -> str:
    try:
        text = path.read_text(errors="replace") + "\n" + extra
    except OSError:
        text = extra
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("$ ")]
    return " | ".join(lines[-n:])[:MESSAGE_MAX]


def run_plan(core: CoreConfig, plan: list[PlanItem], out: Path, source: Source, opts: RunOptions) -> dict:
    return Runner(core, source, out, opts).run(plan)
