"""Turn suites, tiers and configs into a run plan; run sets at a revision; the gate."""
from __future__ import annotations

from contextlib import ExitStack
import datetime as dt
import re
import secrets

from rvw.common.capture import Capture, CaptureError
from pathlib import Path

from rvw.results import write_json, find_results

from .compare import compare
from .captured import adapter_roots, private_storage
from .config import ConfigError, CoreConfig, finite_number
from .known import load_known
from .runner import PlanItem, RunOptions, Runner, job_options, seed_count
from .discover import discover
from .routing import OptionInputs
from .source import WORKTREE, Source, checkout, describe
from .store import resolve_run, results_root


def _check_configs(core: CoreConfig, configs: list[str]) -> None:
    bad = [c for c in configs if core.configs and c not in core.configs]
    if bad:
        raise ConfigError(f"core {core.name}: unknown config(s) {', '.join(bad)} (have: {', '.join(core.configs)})")


def suites_plan(core: CoreConfig, suites: list[str], configs: list[str] | None) -> list[PlanItem]:
    plan = []
    for s in suites:
        suite = core.suite(s)
        cs = configs or core.suite_configs(suite)
        _check_configs(core, cs)
        plan += [PlanItem(suite, c) for c in cs]
    return plan


def tier_plan(core: CoreConfig, tier: str, configs: list[str] | None) -> list[PlanItem]:
    t = core.tier(tier)
    plan = []
    for r in t.runs:
        suite = core.suite(r.suite)
        cs = configs or r.configs or core.suite_configs(suite)
        _check_configs(core, cs)
        plan += [PlanItem(suite, c, list(r.include), r.seeds) for c in cs]
    return plan


def source_for(core: CoreConfig, rev: str | None, source_path: Path | None = None) -> Source:
    """The source tree to run: an explicit path, a revision of the core repo, or the repo as it is."""
    if source_path is not None and rev is not None:
        raise ConfigError("--source and --rev are mutually exclusive")
    if source_path:
        core.require_source_selection()
        return describe(source_path.absolute())
    if core.source_repo is None:
        if rev and rev != WORKTREE:
            raise ConfigError(f"core {core.name}: --rev needs [core] source_repo in {core.path}")
        return Source(None, None, True)
    core.require_source_selection()
    return checkout(core.source_repo, rev or WORKTREE, core.name)


def default_out(core: CoreConfig, label: str, source: Source, root: Path | None = None, *,
                create: bool = True) -> Path:
    """A new, empty run directory under `<results root>/runs`, created here with an exclusive mkdir
    and a random suffix: two runs started in the same second (another seed, config or source) never
    share one (review 10). `create=False` (dry run) only names one, without the suffix."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    rev = (source.short or "norev") + ("-dirty" if source.dirty else "")
    safe = re.sub(r"[^A-Za-z0-9._+-]", "_", label)
    runs = (root or results_root()) / "runs"
    base = f"{stamp}-{core.name}-{safe}-{rev}"
    if not create:
        return runs / base
    runs.mkdir(parents=True, exist_ok=True)
    while True:
        p = runs / f"{base}-{secrets.token_hex(3)}"
        try:
            p.mkdir()
            return p
        except FileExistsError:
            continue


def _stored_plan_problems(core, results, plan, opts, capture):
    """Check requested jobs against pinned evidence, even when both stored sides agree."""
    problems = []
    selected = 0
    option_inputs = OptionInputs(capture, [core.source_repo, *core.cache_paths, *adapter_roots(core)])
    for item in plan:
        suite = item.suite
        def problem(tid, why, **extra):
            problems.append({"suite": suite.name, "config": item.config, "id": tid,
                             "why": why, **extra})
        try:
            tests = discover(suite, item.include + opts.include)
        except (OSError, ValueError) as exc:
            problem("*", f"requested tests cannot be captured: {exc}")
            continue
        if not tests and not opts.include:
            problem("*", "requested suite has no tests")
        selected += len(tests)
        owners = [r for r in results if (r.suite, r.config) == (suite.name, item.config)]
        for owner in owners:
            if sorted(owner.extra.get("perf_metrics") or []) != sorted(suite.perf_metrics):
                problem("*", "requested performance declarations differ or are missing")
            if suite.perf_metrics and owner.extra.get("metric_keys") != {
                    "cycles": suite.cycles_key, "instret": suite.instret_key}:
                problem("*", "requested performance keys differ or are missing")
        options, build_options = job_options(suite, opts), list(suite.build_options)
        try:
            expected_inputs = option_inputs.identities([options, build_options])
        except CaptureError as exc:
            problem("*", str(exc))
            continue
        for owner in owners:
            if owner.extra.get("option_inputs", {}) != expected_inputs:
                problem('*', 'requested option input differs or is missing', paths=sorted(expected_inputs))
        for test in tests:
            entries = [t for r in owners for t in r.tests if t.id == test.id]
            count = seed_count(item, opts)
            wanted_seeds = ([None] if suite.kind == "build" else
                            list(range(opts.seed_base, opts.seed_base + count)))
            if opts.random_seeds and suite.kind != "build":
                if len({t.seed for t in entries if isinstance(t.seed, int) and not isinstance(t.seed, bool)}) < count:
                    problem(test.id, "missing random seeds", seeds=count)
            else:
                for seed in wanted_seeds:
                    if not any(t.seed == seed for t in entries):
                        problem(test.id, "missing test or seed", seed=seed)
                entries = [t for t in entries if t.seed in wanted_seeds]
            digest = None
            if test.elf:
                try:
                    digest = capture.file(test.elf).sha256
                except CaptureError as exc:
                    problem(test.id, str(exc))
                    continue
            for entry in entries:
                recorded = entry.extra.get("options")
                expected = {"max_cycles": None, "mem_latency": None, **options}
                if recorded != expected:
                    problem(test.id, "requested options differ or are missing", seed=entry.seed)
                if entry.extra.get("kind") != suite.kind:
                    problem(test.id, "requested test kind differs or is missing", seed=entry.seed)
                if test.elf and entry.extra.get("elf_sha256") != digest:
                    problem(test.id, "requested ELF hash differs or is missing", seed=entry.seed)
                if suite.kind == "build" and entry.extra.get("build_options") != build_options:
                    problem(test.id, "requested build options differ or are missing")
            if any(bool((r.extra.get("seeds") or {}).get("mode") == "random") != opts.random_seeds
                   for r in owners if suite.kind != "build"):
                problem(test.id, "requested seed mode differs")
    if not selected and not problems:
        problems.append({"suite": "*", "config": "*", "id": "*", "why": "no requested test evidence"})
    return problems


def gate(core: CoreConfig, tier: str, base_rev: str | None, cand_rev: str | None, base_dir: str | None,
         cand_dir: str | None, configs: list[str] | None, opts: RunOptions, known_path: Path | None,
         perf_tolerance: float | None, allow_missing: bool = False, out: Path | None = None,
         seed_policy: str = "auto") -> dict:
    for name, directory, rev in (("base", base_dir, base_rev), ("cand", cand_dir, cand_rev)):
        if directory is not None and rev is not None:
            raise ConfigError(f"--{name} and --{name}-rev are mutually exclusive")
    tol = finite_number(core.perf_tolerance if perf_tolerance is None else perf_tolerance, "perf_tolerance")
    plan = tier_plan(core, tier, configs)
    Runner.check_plan(plan)
    opts.tier = tier
    sides = {}
    known = load_known(known_path)
    # Bind each stored name once, before new runs can change latest or a current pointer.
    refs = dict.fromkeys(ref for ref in (base_dir, cand_dir) if ref)
    paths = {ref: resolve_run(ref, opts.results_root, core=core.name) for ref in refs}
    stored = {side: paths[ref] for side, ref in (("base", base_dir), ("candidate", cand_dir)) if ref}
    pinned = {path: find_results(path) for path in dict.fromkeys(stored.values())}
    stored_results = {side: pinned[path] for side, path in stored.items()}
    root = opts.results_root or results_root()
    root.mkdir(parents=True, exist_ok=True)
    with ExitStack() as owners:
        private = owners.enter_context(private_storage(core, prefix=".rvw-gate-inputs-"))
        capture = Capture(private / "capture")
        plan_problems = [{"side": side, **problem} for side, results in stored_results.items()
                         for problem in _stored_plan_problems(core, results, plan, opts, capture)]
        revisions = {}
        for side, rev, directory in (("base", base_rev, base_dir), ("candidate", cand_rev, cand_dir)):
            if not directory and core.source_repo is not None and (
                    rev == WORKTREE or (side == "candidate" and rev is None)):
                live = describe(core.source_repo)
                if live.rev and not live.dirty and live.reusable:
                    revisions[rev] = capture.git_ref(core.source_repo, live.rev)
            if not directory and rev and rev != WORKTREE and core.source_repo is not None and rev not in revisions:
                revisions[rev] = capture.git_ref(core.source_repo, rev)
        prepared = {}
        for side, rev, directory in (("base", base_rev, base_dir), ("candidate", cand_rev, cand_dir)):
            if directory:
                sides[side] = {"path": str(stored[side]), "ran": False}
                continue
            if side == "base" and rev is None:
                raise ConfigError("gate needs --base-rev or --base")
            src = source_for(core, revisions.get(rev, rev) or WORKTREE)
            output = default_out(core, f"{tier}-{'base' if side == 'base' else 'cand'}", src, opts.results_root)
            runner = owners.enter_context(Runner(core, src, output, opts, capture=capture))
            runner.capture_plan(plan)
            prepared[side] = runner
        # Every side now has its source, ELFs and shared dependencies. Execute only copies.
        for side, runner in prepared.items():
            if opts.log:
                print(f"rvw: gate: {side} {runner.source.short or '?'} from captured inputs -> {runner.out}",
                      file=opts.log, flush=True)
            summary = runner.run(plan)
            sides[side] = {"path": str(runner.out), "ran": True, "run_id": summary["run_id"],
                           "counts": summary.get("counts")}
        capture.verify_tools()
        v = compare(stored_results.get("base", Path(sides["base"]["path"])),
                    stored_results.get("candidate", Path(sides["candidate"]["path"])), known, tol, allow_missing,
                    seed_policy, core=core.name)
        if plan_problems:
            if v.verdict == "accept":
                v.verdict = "inconclusive"
            v.reasons.append("stored_plan_incomplete: stored evidence does not cover the requested plan")
            v.extra["inconclusive_cause"] = "stored_plan_incomplete"
            v.extra["stored_plan_problems"] = plan_problems
            if v.tests != "fail":
                v.tests = "incomplete"
        v.extra["reference_capture"] = {"git_refs": capture.record()["git_refs"],
                                        "tools": capture.record()["tools"]}
        v.extra["gate"] = {"tier": tier, "base": sides["base"], "candidate": sides["candidate"],
                           "known_failures_file": str(known_path) if known_path else None}
        dest = out or Path(sides["candidate"]["path"]) / "verdict.json"
        v.extra["verdict_file"] = str(dest)
        write_json(dest, v.to_dict())
        return {"verdict": v, "file": dest}
