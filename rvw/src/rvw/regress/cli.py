"""`rvw regress`: run suites through a core adapter, compare result sets, gate changes."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from rvw.common import jsonout
from rvw.results.generation import open_current
from rvw.results import SchemaError, find_results, write_json

from .compare import SEED_POLICIES, compare, format_verdict, with_assertion_identity
from .config import ConfigError, load_config
from .discover import discover
from .known import Known, add_known, load_known, remove_known
from .plan import default_out, gate, source_for, suites_plan, tier_plan
from .runner import RunOptions, Runner, run_plan
from .store import read_file, read_index, resolve_run, results_root


def _csv(s: str | None) -> list[str] | None:
    return [x for x in s.split(",") if x] if s else None


def _core_arg(p: argparse.ArgumentParser, required=True):
    p.add_argument("--core", default=None,
                   help="core name (rvw/configs/NAME.toml or $RVW_CORES) or a .toml path; default $RVW_CORE")


def _json_arg(p):
    p.add_argument("--json", action="store_true", help="print JSON on stdout")


def _run_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--jobs", "-j", type=int, help="parallel simulations inside the adapter (default: core config)")
    p.add_argument("--seeds", type=int, help="seeds per test (default: suite config, usually 1)")
    p.add_argument("--seed-base", type=int, default=1, help="first fixed seed (seeds are BASE..BASE+K-1)")
    p.add_argument("--random-seeds", action="store_true", help="draw random seeds (recorded; disables reuse across runs)")
    p.add_argument("--filter", action="append", default=[], help="regex the test id must match (repeatable)")
    p.add_argument("--max-cycles", type=int, help="override the suite's max cycles")
    p.add_argument("--timeout", type=float, help="wall-clock seconds per test (default: suite config)")
    p.add_argument("--replay-max-bytes", type=int,
                   help="maximum unique replay ELF bytes per run (default: 268435456); checked before execution")
    p.add_argument("--rvfi-trace", action="store_true", help="ask the adapter for RVFI traces")
    p.add_argument("--no-cache", action="store_true", help="neither reuse nor store cached results")


def _seed_policy_arg(p) -> None:
    p.add_argument("--seed-policy", choices=SEED_POLICIES, default="auto",
                   help="exact: every base (test, seed) must be in the candidate; count: the candidate runs at "
                        "least as many seeds per test; auto (default): exact unless a side used random seeds")


def _make_opts(a, **kw) -> RunOptions:
    return RunOptions(jobs=a.jobs, seeds=a.seeds, seed_base=a.seed_base, random_seeds=a.random_seeds,
                      include=a.filter, max_cycles=a.max_cycles, timeout_s=a.timeout, rvfi_trace=a.rvfi_trace,
                      replay_max_bytes=a.replay_max_bytes,
                      use_cache=not a.no_cache, log=sys.stderr, **kw)


def register(sub) -> None:
    p = sub.add_parser("regress", help="regression runs, comparisons and the accept/reject gate",
                       description=__doc__)
    rs = p.add_subparsers(dest="regress_cmd", required=True)

    from rvw.sim.cli import register as register_sim
    register_sim(rs)
    from . import random_stream
    random_stream.register(rs)
    from . import sail_tests
    sail_tests.register(rs)
    from rvw.privilege.cli import register as register_privilege
    register_privilege(rs)
    from . import mmu
    mmu.register(rs)
    from . import vector
    vector.register(rs)

    r = rs.add_parser("run", help="run suites or a tier; writes C3 results")
    _core_arg(r)
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--suite", help="suite name(s), comma separated")
    g.add_argument("--tier", help="tier name from the core config (e.g. quick, full)")
    r.add_argument("--config", help="core config(s), comma separated (default: suite/tier default)")
    r.add_argument("--out", type=Path, help="output dir (default $RVW_RESULTS/runs/<stamp>-...); an existing dir is resumed")
    r.add_argument("--rev", help="run the core at this git revision (exported from the core repo)")
    r.add_argument("--source", type=Path, help="core source tree to run (default: the core repo as it is)")
    r.add_argument("--fresh", action="store_true", help="discard what --out already holds")
    r.add_argument("--no-index", action="store_true", help="do not record the run in the history index")
    r.add_argument("--dry-run", action="store_true", help="show what would run (finished, cached, to run); simulate nothing")
    _run_opts(r)
    _json_arg(r)
    r.set_defaults(func=cmd_run)

    c = rs.add_parser("compare", help="compare two result sets; exit 0 accept, 1 reject, 3 inconclusive")
    c.add_argument("base", help="results dir, run set dir, run id, or 'latest'")
    c.add_argument("candidate")
    _core_arg(c, required=False)
    c.add_argument("--known", type=Path, help="known-failures TOML (default: the core config's)")
    c.add_argument("--perf-tolerance", type=float, help="allowed relative perf loss (default: core config or 0.01)")
    c.add_argument("--allow-missing", action="store_true", help="tests absent from the candidate do not reject")
    _seed_policy_arg(c)
    c.add_argument("--out", type=Path, help="where to write verdict.json (default: candidate dir)")
    _json_arg(c)
    c.set_defaults(func=cmd_compare)

    gt = rs.add_parser("gate", help="run a tier on base and candidate revisions and print the verdict")
    _core_arg(gt)
    gt.add_argument("--tier", default="quick")
    gt.add_argument("--base-rev", help="git revision of the core repo for the base")
    gt.add_argument("--base", help="existing base results (dir or run id); mutually exclusive with --base-rev")
    gt.add_argument("--cand-rev", help="candidate commit (default: HEAD when clean; a dirty tree runs but cannot accept)")
    gt.add_argument("--cand", help="existing candidate results; mutually exclusive with --cand-rev")
    gt.add_argument("--config", help="override the tier's configs, comma separated")
    gt.add_argument("--known", type=Path)
    gt.add_argument("--perf-tolerance", type=float)
    gt.add_argument("--allow-missing", action="store_true")
    _seed_policy_arg(gt)
    gt.add_argument("--budget-cpu-seconds", type=float)
    gt.add_argument("--budget-wall-seconds", type=float)
    gt.add_argument("--budget-job-count", type=int)
    gt.add_argument("--cost-report", type=Path)
    _run_opts(gt)
    _json_arg(gt)
    gt.set_defaults(func=cmd_gate)

    k = rs.add_parser("known", help="manage the known-failures file")
    ks = k.add_subparsers(dest="known_cmd", required=True)
    ka = ks.add_parser("add", help="add a known failure, or all failures of a result set (--from)")
    _core_arg(ka, required=False)
    ka.add_argument("--file", type=Path, help="known-failures TOML (default: the core config's)")
    ka.add_argument("--from", dest="from_", help="add every failure in these results (dir or run id)")
    ka.add_argument("--suite")
    ka.add_argument("--id")
    ka.add_argument("--signature")
    ka.add_argument("--config", help="limit the entry to one config")
    ka.add_argument("--reason", required=True)
    ka.add_argument("--rev", help="revision it was recorded at (default: from the results)")
    _json_arg(ka)
    ka.set_defaults(func=cmd_known_add)
    kl = ks.add_parser("list", help="list known failures")
    _core_arg(kl, required=False)
    kl.add_argument("--file", type=Path)
    _json_arg(kl)
    kl.set_defaults(func=cmd_known_list)
    kr = ks.add_parser("remove", help="remove known failures of a test")
    _core_arg(kr, required=False)
    kr.add_argument("--file", type=Path)
    kr.add_argument("--suite", required=True)
    kr.add_argument("--id", required=True)
    kr.add_argument("--signature")
    _json_arg(kr)
    kr.set_defaults(func=cmd_known_remove)

    h = rs.add_parser("history", help="list stored runs (newest first)")
    h.add_argument("--core")
    h.add_argument("--rev", help="core revision prefix")
    h.add_argument("--tier")
    h.add_argument("--limit", type=int, default=20)
    _json_arg(h)
    h.set_defaults(func=cmd_history)

    ls = rs.add_parser("list", help="list a core's suites, tiers and (with --suite) tests")
    _core_arg(ls)
    ls.add_argument("--suite")
    _json_arg(ls)
    ls.set_defaults(func=cmd_list)


def _err(msg: str) -> int:
    print(f"rvw regress: error: {msg}", file=sys.stderr)
    return 2


def _wrap(fn):
    def inner(a):
        try:
            if fn.__name__ != "cmd_history" and not a.core and not getattr(a, "project", None):
                from rvw.common.project import find_project
                a.project = find_project()
                if a.project is None:
                    a.core = os.environ.get("RVW_CORE")
            return fn(a)
        except (ConfigError, SchemaError, ValueError, RuntimeError, FileNotFoundError) as e:
            if getattr(a, "structured", False):
                raise
            return _err(str(e))
    inner.__name__ = fn.__name__
    return inner


def _emit(a, obj, text: str) -> None:
    if getattr(a, "structured", False):
        a.result = obj
    elif a.json:
        jsonout.write(obj, indent=2)    # JsonOutputError (a ValueError): _wrap exits 2, stdout empty
    else:
        print(text)


@_wrap
def cmd_run(a):
    core = load_config(a.core, project=getattr(a, "project", None))
    configs = _csv(a.config)
    plan = tier_plan(core, a.tier, configs) if a.tier else suites_plan(core, _csv(a.suite), configs)
    out = a.out
    previous = open_current(out) if out and (out / "current").exists() and not a.fresh else None
    if out and (out / "run.json").is_file() and not a.fresh:
        if previous is not None:
            prev = json.loads(previous.read_bytes("run.json"))
        else:
            prev = json.loads(read_file(out / "run.json"))
        src = source_for(core, a.rev, a.source or (Path(prev["source"]["core_repo"]) if prev["source"].get("core_repo") and not a.rev else None))
    else:
        src = source_for(core, a.rev, a.source)
    label = a.tier or "+".join(dict.fromkeys(p.suite.name for p in plan))
    opts = _make_opts(a, tier=a.tier, fresh=a.fresh, index=not a.no_index, previous_generation=previous)
    out = out or default_out(core, label, src, create=not a.dry_run)
    if a.dry_run:
        pv = Runner(core, src, out, opts).preview(plan)
        lines = [f"{r['suite']}/{r['config']}: {r['jobs']} jobs, {r['done']} done, {r['cached']} cached, "
                 f"{r['to_run']} to run" for r in pv["plan"]]
        lines.append(f"source {src.short or '?'}{' (dirty, no cache)' if not pv['cacheable'] else ''}; out {out}")
        _emit(a, pv, "\n".join(lines))
        return 0
    summary = run_plan(core, plan, out, src, opts)
    summary["path"] = str(out.resolve())
    lines = [f"{r['suite']}/{r['config']}: " + ", ".join(f"{v} {k}" for k, v in r["counts"].items())
             + (f" ({r['inconclusive']} inconclusive)" if r.get("inconclusive") else "")
             for r in summary["results"]]
    state = ("all passed" if summary["ok"] else "FAILURES" if set(summary["counts"]) - {"pass"}
             else "INCONCLUSIVE (passes that prove nothing)")
    lines.append(f"results: {summary['path']}  ({state})")
    _emit(a, summary, "\n".join(lines))
    return 0 if summary["ok"] else 1


def _known_file(a, explicit: Path | None) -> Path | None:
    if explicit:
        return explicit
    if a.core or getattr(a, "project", None):
        return load_config(a.core, project=getattr(a, "project", None)).known_failures
    return None


@_wrap
def cmd_compare(a):
    core = load_config(a.core, project=getattr(a, "project", None)) if (a.core or getattr(a, "project", None)) else None
    name = core.name if core else None
    resolved = {ref: resolve_run(ref, core=name) for ref in dict.fromkeys((a.base, a.candidate))}
    base, cand = resolved[a.base], resolved[a.candidate]
    known_path = a.known or (core.known_failures if core else None)
    tol = a.perf_tolerance
    if tol is None:
        tol = core.perf_tolerance if core else 0.01
    v = compare(base, cand, load_known(known_path), tol, a.allow_missing, a.seed_policy, core=name)
    v.extra["known_failures_file"] = str(known_path) if known_path else None
    dest = a.out or (cand / "verdict.json" if cand.is_dir() else None)
    if dest:
        write_json(dest, v.to_dict())
    text = format_verdict(v) + (f"\nverdict: {dest}" if dest else "")
    _emit(a, v.to_dict(), text)
    return v.exit_code


@_wrap
def cmd_gate(a):
    limits = {key: getattr(a, "budget_" + key, None) for key in ("cpu_seconds", "wall_seconds", "job_count")}
    if any(value is not None for value in limits.values()) or getattr(a, "cost_report", None):
        import tempfile
        from rvw.common.budget import Budget, supervise
        Budget(**limits)
        with tempfile.TemporaryDirectory(prefix="rvw-gate-budget-") as directory:
            request, output = Path(directory) / "request.json", Path(directory) / "result.json"
            options = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()
                       if k not in ("func", "command", "regress_cmd", "json", "structured", "cost_report")
                       and not k.startswith("budget_")}
            request.write_text(json.dumps({"module": "rvw.regress.cli", "function": "execute_json", "arguments": {"action": "gate", **options}}))
            report = getattr(a, "cost_report", None) or Path.cwd() / "gate-cost.json"
            rc = supervise([sys.executable, "-m", "rvw.mcp.worker", str(request), str(output)], Budget(**limits), report)
            cost = json.loads(Path(report).read_text())
            if rc or cost["status"] != "complete" or not output.is_file():
                value = {"verdict": "inconclusive", "tests": "incomplete", "causes": [cost["reason"]], "cost": cost}
                _emit(a, value, "INCONCLUSIVE: budget or worker stopped")
                return 3
            envelope = json.loads(output.read_text())
            if "result" not in envelope:
                raise ValueError(envelope.get("error", "worker result missing"))
            value = {**envelope["result"], "cost": cost}
            _emit(a, value, str(value.get("verdict", "inconclusive")))
            return {"accept": 0, "reject": 1}.get(value.get("verdict"), 3)
    core = load_config(a.core, project=getattr(a, "project", None))
    opts = _make_opts(a)
    known = a.known or core.known_failures
    r = gate(core, a.tier, a.base_rev, a.cand_rev, a.base, a.cand, _csv(a.config), opts, known,
             a.perf_tolerance, a.allow_missing, seed_policy=a.seed_policy)
    v = r["verdict"]
    _emit(a, v.to_dict(), format_verdict(v) + f"\nverdict: {r['file']}")
    return v.exit_code


@_wrap
def cmd_known_add(a):
    path = _known_file(a, a.file)
    if path is None:
        raise ValueError("give --file or --core (with known_failures in its config)")
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = []
    if a.from_:
        if a.signature is not None:
            raise ValueError("--from and --signature are mutually exclusive")
        core = load_config(a.core, project=getattr(a, "project", None)).name if (a.core or getattr(a, "project", None)) else None
        results = find_results(resolve_run(a.from_, core=core))
        cores = {res.core for res in results}
        if len(cores) != 1 or any(not name.strip() for name in cores):
            raise ValueError("known-failure results must name one non-empty core")
        if core is not None and cores != {core}:
            raise ValueError(f"results core {next(iter(cores))!r} differs from requested core {core!r}")
        for res in results:
            if (a.suite and res.suite != a.suite) or (a.config and res.config != a.config):
                continue
            seen = set()
            for original in res.tests:
                t = with_assertion_identity(original)
                if not t.failed or not t.conclusive or (a.id and t.id != a.id) or (t.id, t.signature) in seen:
                    continue
                seen.add((t.id, t.signature))
                entries.append(Known(suite=res.suite, id=t.id, signature=t.signature, reason=a.reason,
                                     recorded_at_rev=a.rev or res.source.get("core_rev") or "",
                                     config=res.config, recorded_at=now))
        if not entries:
            raise ValueError("no matching conclusive failures to import")
    else:
        if not (a.suite and a.id and a.signature):
            raise ValueError("give --suite, --id and --signature, or --from RESULTS")
        entries.append(Known(suite=a.suite, id=a.id, signature=a.signature, reason=a.reason,
                             recorded_at_rev=a.rev or "", config=a.config, recorded_at=now))
    added, replaced = add_known(path, entries)
    _emit(a, {"file": str(path), "added": added, "replaced": replaced, "entries": [e.to_dict() for e in entries]},
          f"{path}: {added} added, {replaced} replaced")
    return 0


@_wrap
def cmd_known_list(a):
    path = _known_file(a, a.file)
    entries = load_known(path)
    text = "\n".join(f"{e.suite}/{e.id}{'@' + e.config if e.config else ''}  {e.signature}  "
                     f"[{e.recorded_at_rev}] {e.reason}" for e in entries) or f"no known failures ({path})"
    _emit(a, {"file": str(path) if path else None, "known": [e.to_dict() for e in entries]}, text)
    return 0


@_wrap
def cmd_known_remove(a):
    path = _known_file(a, a.file)
    if path is None:
        raise ValueError("give --file or --core")
    n = remove_known(path, a.suite, a.id, a.signature)
    _emit(a, {"file": str(path), "removed": n}, f"{path}: {n} removed")
    return 0


@_wrap
def cmd_history(a):
    from rvw.common.project import load_project
    project = load_project(getattr(a, "project", None), core=a.core)
    name = project.name if project else a.core
    entries = list(reversed(read_index()))
    if name:
        entries = [e for e in entries if e.get("core") == name]
    if a.rev:
        entries = [e for e in entries if (e.get("core_rev_full") or e.get("core_rev") or "").startswith(a.rev)]
    if a.tier:
        entries = [e for e in entries if e.get("tier") == a.tier]
    entries = entries[: a.limit]
    for e in entries:
        e["exists"] = Path(e["path"]).is_dir()
    lines = []
    for e in entries:
        counts = ", ".join(f"{v} {k}" for k, v in (e.get("counts") or {}).items()) or "unfinished"
        rev = (e.get("core_rev") or "?") + ("+dirty" if e.get("core_dirty") else "")
        lines.append(f"{e['run_id']}  {rev}  {'ok' if e.get('ok') else 'FAIL'}  {counts}"
                     + ("" if e["exists"] else "  (deleted)"))
        lines.append(f"    {e['path']}")
    _emit(a, {"root": str(results_root()), "runs": entries},
          "\n".join(lines) or f"no runs indexed under {results_root()}")
    return 0


@_wrap
def cmd_list(a):
    core = load_config(a.core, project=getattr(a, "project", None))
    if a.suite:
        s = core.suite(a.suite)
        tests = discover(s)
        _emit(a, {"suite": s.name, "tests": [{"id": t.id, "elf": str(t.elf) if t.elf else None} for t in tests]},
              "\n".join(t.id for t in tests))
        return 0
    suites = []
    for s in core.suites.values():
        try:
            n = len(discover(s))
        except ConfigError as e:
            n = None
        suites.append({"name": s.name, "kind": s.kind, "description": s.description, "tests": n,
                       "configs": core.suite_configs(s), "seeds": s.seeds, "dir": str(s.dir) if s.dir else None})
    tiers = [{"name": t.name, "description": t.description,
              "runs": [{"suite": r.suite, "configs": r.configs, "include": r.include, "seeds": r.seeds} for r in t.runs]}
             for t in core.tiers.values()]
    lines = [f"core {core.name} ({core.path})", f"adapter: {' '.join(core.adapter)}",
             f"configs: {', '.join(core.configs)} (default {core.default_config})", "suites:"]
    lines += [f"  {s['name']:<16} {s['kind']:<8} {s['tests'] if s['tests'] is not None else 'n/a':>5} tests  "
              f"configs {','.join(s['configs'])}  {s['description']}" for s in suites]
    lines.append("tiers:")
    lines += [f"  {t['name']:<8} {t['description']}" for t in tiers]
    _emit(a, {"core": core.name, "path": str(core.path), "adapter": core.adapter, "configs": core.configs,
              "default_config": core.default_config, "suites": suites, "tiers": tiers}, "\n".join(lines))
    return 0


def execute_json(action: str, **options) -> dict:
    """Run the same command handlers as the CLI, returning their JSON without printing.

    Each invocation owns its result sink; concurrent MCP requests never redirect stdout.
    """
    defaults = dict(core=None, project=None, suite=None, tier=None, config=None,
                    out=None, rev=None, source=None, fresh=False, no_index=False, dry_run=False,
                    jobs=None, seeds=None, seed_base=1, random_seeds=False, filter=[],
                    max_cycles=None, timeout=None, rvfi_trace=False, no_cache=False, replay_max_bytes=None,
                    known=None, perf_tolerance=None, allow_missing=False, seed_policy="auto", base_rev=None,
                    cand_rev=None, base=None, cand=None, candidate=None, file=None, from_=None,
                    id=None, signature=None, reason=None, limit=20,
                    budget_cpu_seconds=None, budget_wall_seconds=None, budget_job_count=None, cost_report=None)
    unknown = options.keys() - defaults.keys()
    if unknown:
        raise TypeError(f"unknown options: {sorted(unknown)}")
    defaults.update(options)
    required = {"compare": ("base", "candidate"), "known_add": ("reason",),
                "known_remove": ("suite", "id")}.get(action, ())
    missing = [key for key in required if defaults[key] is None]
    if missing:
        raise TypeError(f"missing required options: {', '.join(missing)}")
    if action == "run" and bool(defaults["suite"]) == bool(defaults["tier"]):
        raise ValueError("give exactly one of suite or tier")
    if action == "gate" and not defaults["tier"]:
        defaults["tier"] = "quick"
    for key in ("out", "source", "known", "file"):
        if defaults[key] is not None:
            defaults[key] = Path(defaults[key])
    args = argparse.Namespace(**defaults, json=True, structured=True)
    handlers = {"run": cmd_run, "compare": cmd_compare, "gate": cmd_gate,
                "list": cmd_list, "history": cmd_history, "known_list": cmd_known_list,
                "known_add": cmd_known_add, "known_remove": cmd_known_remove}
    handlers[action](args)
    return args.result
