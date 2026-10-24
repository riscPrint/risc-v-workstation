"""Compare two result sets (C3) into a verdict (C4).

Tests are matched on (suite, config, id). Program hashes and stimulus options must agree for
each compared seed. Missing input identity or changed inputs make that test inconclusive.
Seeds are checked before anything is aggregated: with
fixed seeds every (test, seed) of the base must be in the candidate, else it is `missing` (a
dropped failing seed is never "fixed"). With random seeds on either side (or `seed_policy="count"`)
the candidate must run at least as many seeds per test as the base. Different seed sets still
give inconclusive evidence; counts alone cannot prove equal inputs.

A conclusive candidate failure is:
  - known       its (suite, id, signature) is in the known-failures file;
  - still failing  the base failed the same test and seed with the same signature (conclusively);
  - new         anything else (including a different signature of a test that already failed).
An inconclusive candidate result (harness `error`, a result rvw wrote itself, a wall-clock
timeout, an adapter `inconclusive` mark) proves nothing about the core, whatever its status: it is
never known, still failing or a pass, and a base failure is fixed only by a conclusive pass of
every failing seed.

Verdict: `reject` on new failures, missing tests or seeds, or performance regressions beyond the
tolerance; else `inconclusive` when a candidate result is inconclusive, a configured performance
metric is missing for a compared seed (on either side), the two sides declare different metrics
(the union is compared), no test ran on both sides, or either source lacks a clean committed
identity; else `accept`.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from pathlib import Path

from rvw.results import SuiteResults, TestEntry, Verdict, find_results, inconclusive_cause
from rvw.results.signature import failure_signature, located_assertion

from .config import finite_number, metric_specs
from .known import Known

Key = tuple[str, str, str]  # suite, config, id
SEED_POLICIES = ("auto", "exact", "count")


def _source_identity(r: SuiteResults) -> str:
    # A checkout location does not identify its content. Keep every other recorded source
    # field, including full revisions, dirty fingerprints, links, adapter and tool identities.
    source = {k: v for k, v in r.source.items() if k != "core_repo"}
    if source.get("core_rev_full"):
        source["core_rev"] = source.pop("core_rev_full")
    return json.dumps([r.core, source], sort_keys=True)


def with_assertion_identity(t: TestEntry) -> TestEntry:
    """Derive assertion identity from complete saved evidence, without changing the input."""
    if t.status != "assert":
        return t
    message = t.extra.get("message")
    if isinstance(message, str) and message:
        # Old C3 fingerprints dropped HDL lines and truncated messages.
        return replace(t, signature=failure_signature("assert", message=message))
    if not located_assertion(t.signature):
        return replace(t, extra={**t.extra, "inconclusive":
                       "assertion identity needs a source location or full message; rerun"})
    return t


def _group(results: list[SuiteResults], side: str) -> tuple[dict[Key, list[TestEntry]], dict, dict]:
    identities = {_source_identity(r) for r in results}
    if len(identities) != 1:
        raise ValueError(f"{side} has inconsistent source identity; select results from one source")
    if len(results) > 1 and not any(results[0].source.get(k) for k in
                                    ("core_rev_full", "core_rev", "core_fingerprint", "adapter_identity")):
        raise ValueError(f"{side} source identity is unknown; cannot combine several result sets")
    if len(results) > 1 and results[0].source.get("core_dirty") and not any(
            results[0].source.get(k) for k in ("core_fingerprint", "adapter_identity")):
        raise ValueError(f"{side} source identity has no dirty fingerprint; cannot combine result sets")
    tests: dict[Key, list[TestEntry]] = {}
    owner: dict[tuple[Key, int | None], SuiteResults] = {}
    perf: dict[tuple[str, str], list[str]] = {}
    modes: dict[tuple[str, str], bool] = {}
    designs: dict[tuple[str, str], set] = {}
    for r in results:
        suite = (r.suite, r.config)
        metrics = sorted(set(r.extra.get("perf_metrics") or []))
        random = _random_seeds(r)
        if suite in perf and (perf[suite] != metrics or modes[suite] != random):
            raise ValueError(f"{side} has inconsistent performance metrics or seed modes for "
                             f"{r.suite}/{r.config}")
        perf[suite], modes[suite] = metrics, random
        for original in r.tests:
            t = with_assertion_identity(original)
            k = (r.suite, r.config, t.id)
            sample = (k, t.seed)
            if sample in owner:
                previous = owner[sample]
                raise ValueError(f"{side} has duplicate {r.suite}/{r.config}/{t.id} seed {t.seed} "
                                 f"in {previous.path or previous.run_id} and {r.path or r.run_id}")
            tests.setdefault(k, []).append(t)
            owner[sample] = r
            designs.setdefault(suite, set()).add((t.extra.get("rtl_sha256"), t.extra.get("adapter_identity")))
    for (suite, config), models in designs.items():
        # One suite/config is one model. Pooled shards of another design (RTL hash or adapter
        # identity, including a missing one) are not one result set.
        if len(models) > 1:
            raise ValueError(f"{side} has results of more than one design (rtl_sha256 or adapter "
                             f"identity) for {suite}/{config}; select results from one design")
    return tests, owner, perf


def _run_path(owner: SuiteResults, t: TestEntry) -> str | None:
    if not t.run:
        return None
    return str((owner.path / t.run)) if owner.path else t.run


def _metric(t: TestEntry, name: str):
    # Canonical fields use the configured selector, even when C1 also has metrics.cycles.
    v = getattr(t, name) if name in ("cycles", "instret", "wall_s") else t.metrics.get(name)
    try:
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None
    except OverflowError:
        return None


def _metric_origin(t: TestEntry, name: str) -> str | None:
    origins = t.extra.get("metric_origins")
    origin = origins.get(name) if isinstance(origins, dict) else None
    if isinstance(origin, str) and origin:
        return json.dumps(origin)
    if (isinstance(origin, dict) and set(origin) == {"operation", "instret", "cycles"}
            and origin["operation"] == "instret/cycles"
            and all(isinstance(origin[key], str) and origin[key] for key in ("instret", "cycles"))):
        return json.dumps(origin, sort_keys=True)
    return None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _rev(results: list[SuiteResults]) -> str | None:
    revs = {(r.source.get("core_rev"), bool(r.source.get("core_dirty"))) for r in results}
    if len(revs) != 1:
        return None
    rev, dirty = revs.pop()
    return f"{rev}{'+dirty' if dirty else ''}" if rev else None


def _random_seeds(r: SuiteResults | None) -> bool:
    seeds = r.extra.get("seeds") if r else None
    return isinstance(seeds, dict) and seeds.get("mode") == "random"


def _by_seed(entries: list[TestEntry]) -> dict:
    """Entries per seed, after `_group` has refused duplicate samples."""
    return {t.seed: t for t in entries}


def _input_identity(t: TestEntry) -> str | None:
    """Program and stimulus identity, independent of status, metrics and checkout paths."""
    options = t.extra.get("options")
    if not isinstance(options, dict):
        return None
    if t.extra.get("kind") == "build":
        flags = t.extra.get("build_options")
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            return None
        identity = ["build", flags, options]
    else:
        if not isinstance(t.seed, int) or isinstance(t.seed, bool):
            return None
        digest = t.extra.get("elf_sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            return None
        identity = ["elf", digest, options]
    try:
        return json.dumps(identity, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return None


def _why_inconclusive(t: TestEntry) -> str:
    """The reason of the shared rule (`inconclusive_cause`, as `TestEntry.conclusive`)."""
    return inconclusive_cause(t.status, t.extra, t.signature) or "inconclusive"


def _metric_specs(base: list[str] | None, cand: list[str] | None) -> dict[str, tuple[str | None, str]]:
    """The union of both sides' metric declarations ("name[:direction]"): name -> (direction, who
    declares it). Review 5: the candidate's list replaced the base's, so a metric the candidate
    dropped was never checked. `who` is "both", "declared on the base only", "declared on the
    candidate only" or a direction conflict (then direction is None)."""
    b = metric_specs(base if base is not None else [])
    c = metric_specs(cand if cand is not None else [])
    out: dict[str, tuple[str | None, str]] = {}
    for name in [*b, *(n for n in c if n not in b)]:
        if name in b and name in c:
            out[name] = (b[name], "both") if b[name] == c[name] else (
                None, f"declared with different directions (base {b[name]}, candidate {c[name]})")
        else:
            out[name] = (b.get(name) or c.get(name), "declared on the base only" if name in b else "declared on the candidate only")
    return out


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _require_committed(v: Verdict, base: list[SuiteResults], cand: list[SuiteResults]) -> Verdict:
    uncommitted = [side for side, results in (("base", base), ("candidate", cand))
                   if any(r.source.get("core_dirty") is not False
                          or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}",
                                          str(r.source.get("core_rev_full", ""))) is None for r in results)]
    if uncommitted:
        if v.verdict == "accept":
            v.verdict = "inconclusive"
        hint = "commit (a scratch branch is fine) and rerun"
        v.reasons.append(f"candidate_not_committed: {', '.join(uncommitted)} lacks a clean committed identity; {hint}")
        v.extra.setdefault("inconclusive_cause", "candidate_not_committed")
        v.extra["uncommitted_sides"] = uncommitted
        v.extra["hint"] = hint
        if v.verdict == "inconclusive":
            v.not_accepted_reason = "uncommitted"
    return v


def compare(base: Path | list[SuiteResults], cand: Path | list[SuiteResults], known: list[Known] | None = None,
            perf_tolerance: float = 0.01, allow_missing: bool = False, seed_policy: str = "auto", *,
            core: str | None = None) -> Verdict:
    perf_tolerance = finite_number(perf_tolerance, "perf_tolerance")
    if seed_policy not in SEED_POLICIES:
        raise ValueError(f"seed policy must be one of {', '.join(SEED_POLICIES)}")
    base_res = base if isinstance(base, list) else find_results(base)
    cand_res = (cand if isinstance(cand, list) else
                base_res if not isinstance(base, list) and str(base) == str(cand) else find_results(cand))
    if not base_res:
        raise ValueError(f"no results.json under {base}")
    if not cand_res:
        raise ValueError(f"no results.json under {cand}")
    for result in [*base_res, *cand_res]:
        metric_specs(result.extra.get("perf_metrics", []))
    if any(not isinstance(r.core, str) or not r.core.strip() for r in [*base_res, *cand_res]):
        raise ValueError("base and candidate results must record a non-empty core name")
    for side, results in (("base", base_res), ("candidate", cand_res)):
        if len({r.core for r in results}) != 1:
            raise ValueError(f"{side} has inconsistent source identity; core names differ")
    cores = {r.core for r in [*base_res, *cand_res]}
    if len(cores) != 1:
        raise ValueError(f"base and candidate core names differ: {', '.join(sorted(cores))}")
    if core is not None and cores != {core}:
        raise ValueError(f"results core {next(iter(cores))!r} differs from requested core {core!r}")
    # Equal uncovered identities do not identify equal inputs (review 16). Refuse the
    # aggregation itself, before an old failing shard can cover a current failure.
    incomplete = [side for side, rs in (("base", base_res), ("candidate", cand_res))
                  if len(rs) > 1 and any(r.source.get("identity_complete") is False
                                         or r.source.get("core_identity_covered") is False for r in rs)]
    if incomplete:
        v = Verdict("inconclusive", reasons=[f"{side} source identity is incomplete; cannot combine result sets"
                                             for side in incomplete])
        v.extra = {"compared": 0, "seed_policy": seed_policy,
                   "base": {"paths": sorted({str(r.path) for r in base_res if r.path}),
                            "core_rev": _rev(base_res), "tests": sum(len(r.tests) for r in base_res)},
                   "candidate": {"paths": sorted({str(r.path) for r in cand_res if r.path}),
                                 "core_rev": _rev(cand_res), "tests": sum(len(r.tests) for r in cand_res)}}
        v.extra["known_capture"] = getattr(known, "capture", None)
        v.extra["generations"] = _generations(base_res, cand_res)
        return _require_committed(v, base_res, cand_res)
    known = known if known is not None else []
    bt, bown, bperf = _group(base_res, "base")
    ct, cown, cperf = _group(cand_res, "candidate")

    new, fixed, known_hits, still, missing, added, perf, inconclusive = [], [], [], [], [], [], [], []
    compared = 0  # tests present on both sides with at least one conclusive candidate result
    for k in sorted(set(bt) | set(ct)):
        suite, config, tid = k
        b, c = bt.get(k), ct.get(k)
        if c is None:
            missing.append({"suite": suite, "config": config, "id": tid,
                            "base_status": "fail" if any(t.failed for t in b) else "pass"})
            continue
        bs, cs = _by_seed(b or []), _by_seed(c)
        random = any(_random_seeds(owners[(k, t.seed)])
                     for entries, owners in ((b or [], bown), (c, cown)) for t in entries)
        exact = seed_policy == "exact" or (seed_policy == "auto" and not random)
        seeds_complete = True
        if b is not None:
            if exact:
                for s in sorted(set(bs) - set(cs), key=lambda x: (x is None, x)):
                    missing.append({"suite": suite, "config": config, "id": tid, "seed": s,
                                    "base_status": "fail" if bs[s].failed else "pass"})
                    seeds_complete = False
            elif len(cs) < len(bs):
                missing.append({"suite": suite, "config": config, "id": tid,
                                "seeds": {"base": len(bs), "candidate": len(cs)},
                                "base_status": "fail" if any(t.failed for t in b) else "pass"})
                seeds_complete = False
            changed = [s for s in bs.keys() & cs.keys()
                       if _input_identity(bs[s]) is None or _input_identity(cs[s]) is None
                       or _input_identity(bs[s]) != _input_identity(cs[s])]
            if changed or (not exact and bs.keys() != cs.keys()):
                inconclusive.append({"suite": suite, "config": config, "id": tid,
                                     "why": "test inputs differ or are missing (ELF hash, seed or options); "
                                            "rerun both sides with the same inputs"})
                continue
            if any(t.conclusive and t.seed in bs for t in c):
                compared += 1
        b_conclusive_sigs = {t.signature for t in (b or []) if t.failed and t.conclusive}
        b_all_sigs = {t.signature for t in (b or []) if t.failed}
        seen, seen_inc, classified = set(), set(), set()
        for t in sorted(c, key=lambda x: (x.seed is None, x.seed if x.seed is not None else 0)):
            # Inconclusive first, whatever the status: an untrusted pass is no pass (review 5).
            if t.conclusive and not t.failed:
                continue
            item = {"suite": suite, "config": config, "id": tid, "signature": t.signature, "status": t.status,
                    "seed": t.seed, "run": _run_path(cown[(k, t.seed)], t)}
            if t.extra.get("message"):
                item["message"] = t.extra["message"]
            if not t.conclusive:
                if (t.status, t.signature) not in seen_inc:
                    seen_inc.add((t.status, t.signature))
                    inconclusive.append({**item, "why": _why_inconclusive(t)})
                continue
            seen.add(t.signature)
            hit = next((kn for kn in known if kn.matches(suite, tid, t.signature, config)), None)
            if hit:
                if ("known", t.signature) not in classified:
                    known_hits.append({**item, "reason": hit.reason, "recorded_at_rev": hit.recorded_at_rev})
                    classified.add(("known", t.signature))
            elif (t.seed in bs and bs[t.seed].conclusive and bs[t.seed].failed
                  and t.signature == bs[t.seed].signature):
                if ("still", t.signature) not in classified:
                    still.append(item)
                    classified.add(("still", t.signature))
            else:
                if b is None:
                    item["base"] = "absent"
                else:
                    item["base"] = "pass" if not b_all_sigs else "failed differently: " + ", ".join(sorted(map(str, b_all_sigs)))
                if ("new", t.signature) not in classified:
                    new.append(item)
                    classified.add(("new", t.signature))
        if b is None:
            if not seen and not seen_inc:
                added.append({"suite": suite, "config": config, "id": tid})
            continue
        # Fixed: a conclusive base failure that the candidate no longer shows. With exact seeds, every
        # failing base seed must have been rerun and passed; otherwise the item says it was not rerun.
        for sig in sorted(b_conclusive_sigs - seen, key=str):
            failing = [t for t in b if t.failed and t.conclusive and t.signature == sig]
            if all(s.seed in cs and cs[s.seed].conclusive and not cs[s.seed].failed for s in failing):
                fixed.append({"suite": suite, "config": config, "id": tid, "signature": sig,
                              "seeds": sorted(s.seed for s in failing if s.seed is not None),
                              "run": _run_path(bown[(k, failing[0].seed)], failing[0])})
        # Performance: only when the test passed on every seed on both sides.
        metrics = _metric_specs(bperf.get((suite, config)), cperf.get((suite, config)))
        if metrics and not seen and not seen_inc and seeds_complete:
            if bs.keys() != cs.keys():
                inconclusive.append({"suite": suite, "config": config, "id": tid,
                                     "why": "performance means require the same seed set on both sides"})
                continue
            if any(not t.conclusive for t in b):
                inconclusive.append({"suite": suite, "config": config, "id": tid, "signature": None,
                                     "status": "pass", "why": "the base has no usable result to compare performance"})
                continue
            if b_all_sigs:
                continue
            for name, (direction, declared_by) in metrics.items():
                # Declared on one side only, or with different directions: the gate cannot accept.
                if declared_by != "both":
                    inconclusive.append({"suite": suite, "config": config, "id": tid, "signature": None,
                                         "status": "pass", "metric": name,
                                         "why": f"performance metric {name} {declared_by}"})
                    if direction is None:
                        continue
                higher_better = direction in ("max", "higher")
                # A configured metric must be there for every compared seed on both sides: a seed
                # without it would make the mean (or the whole check) silently skip a regression.
                lacking = [f"{side} seed {t.seed}" for side, ts in (("base", b), ("candidate", c))
                           for t in ts if _metric(t, name) is None]
                if lacking:
                    inconclusive.append({"suite": suite, "config": config, "id": tid, "signature": None,
                                         "status": "pass", "metric": name,
                                         "why": f"performance metric {name} missing ({', '.join(lacking)})"})
                    continue
                origins = {_metric_origin(t, name) for t in [*b, *c]}
                if None in origins or len(origins) != 1:
                    inconclusive.append({"suite": suite, "config": config, "id": tid, "metric": name,
                                         "why": f"performance metric {name} origins differ or are missing"})
                    continue
                if any(_metric(t, name) <= 0 for t in [*b, *c]):
                    inconclusive.append({"suite": suite, "config": config, "id": tid, "metric": name,
                                         "why": f"performance metric {name} must be positive for relative comparison"})
                    continue
                bv = _mean(_metric(t, name) for t in b)
                cv = _mean(_metric(t, name) for t in c)
                if not math.isfinite(bv) or not math.isfinite(cv):
                    inconclusive.append({"suite": suite, "config": config, "id": tid, "metric": name,
                                         "why": "performance metric mean is not finite"})
                    continue
                change = (cv - bv) / bv
                if not math.isfinite(change):
                    inconclusive.append({"suite": suite, "config": config, "id": tid, "metric": name,
                                         "why": "relative performance change is not finite"})
                    continue
                worse = -change if higher_better else change
                perf.append({"suite": suite, "config": config, "id": tid, "metric": name,
                             "base": round(bv, 4) if isinstance(bv, float) and not bv.is_integer() else int(bv),
                             "candidate": round(cv, 4) if isinstance(cv, float) and not cv.is_integer() else int(cv),
                             "change": round(change, 5), "regression": worse > perf_tolerance})

    reasons = []
    if new:
        reasons.append(f"{_plural(len(new), 'new failure')}")
    if missing and not allow_missing:
        reasons.append(f"{_plural(len(missing), 'test')} missing from the candidate"
                       if all("seed" not in m and "seeds" not in m for m in missing)
                       else f"{_plural(len(missing), 'test or seed')} missing from the candidate")
    for p in perf:
        if p["regression"]:
            reasons.append(f"{p['id']} {p['metric']} {p['change']:+.1%} > {perf_tolerance:.1%}"
                           + (f" ({p['suite']}/{p['config']})" if len({(q['suite'], q['config']) for q in perf}) > 1 else ""))
    unsure = []
    if inconclusive:
        unsure.append(f"{_plural(len(inconclusive), 'inconclusive result')} (harness errors, wall-clock timeouts, "
                      "results rvw wrote itself, adapter-marked results, or missing or differently declared performance "
                      "metrics prove nothing about the core)")
    if compared == 0:
        n_c = sum(len(r.tests) for r in cand_res)
        unsure.append("no test ran on both sides" if n_c else "the candidate has no test results")
    if any(r.source.get("identity_complete") is False or r.source.get("core_identity_covered") is False
           for r in [*base_res, *cand_res]):
        unsure.append("input_not_captured:source_identity: an input source identity is incomplete")
    verdict = "reject" if reasons else ("inconclusive" if unsure else "accept")
    v = Verdict(verdict, new_failures=new, fixed=fixed, known_failures=known_hits,
                missing=missing, perf=perf, reasons=reasons + unsure, inconclusive=inconclusive,
                tests={"accept": "pass", "reject": "fail", "inconclusive": "incomplete"}[verdict])
    v.extra = {
        "still_failing": still, "added": added, "perf_tolerance": perf_tolerance, "allow_missing": allow_missing,
        "seed_policy": seed_policy, "compared": compared,
        "base": {"paths": sorted({str(r.path) for r in base_res if r.path}), "core_rev": _rev(base_res),
                 "tests": sum(len(r.tests) for r in base_res)},
        "candidate": {"paths": sorted({str(r.path) for r in cand_res if r.path}), "core_rev": _rev(cand_res),
                      "tests": sum(len(r.tests) for r in cand_res)},
    }
    v.extra["known_capture"] = getattr(known, "capture", None)
    v.extra["generations"] = _generations(base_res, cand_res)
    return _require_committed(v, base_res, cand_res)


def _generations(base, head):
    return {side: sorted({r.generation for r in results if r.generation})
            for side, results in (("base", base), ("head", head))}


def format_verdict(v: Verdict) -> str:
    b, c = v.extra.get("base", {}), v.extra.get("candidate", {})
    still = v.extra.get("still_failing", [])
    summary = (f"{v.extra.get('compared', 0)} compared, {len(v.new_failures)} new failures, "
               f"{len(still)} still failing")
    if still:
        summary += " (" + ", ".join(dict.fromkeys(i["id"] for i in still)) + ")"
    if v.tests == "pass" and v.not_accepted_reason == "uncommitted":
        sides = " and ".join("the " + side for side in v.extra.get("uncommitted_sides", [])) or "the source"
        out = [f"TESTS PASS: {summary}.",
               f"NOT ACCEPTED: {sides} lacks a clean committed identity. "
               "Commit (a scratch branch is fine) and rerun; passing results can be reused."]
    else:
        headline = {"accept": "ACCEPT", "reject": "REJECT", "inconclusive": "INCONCLUSIVE"}[v.verdict]
        if v.verdict == "inconclusive":
            cause = v.extra.get("inconclusive_cause")
            if cause == "candidate_not_committed" and v.tests == "incomplete":
                cause = None
            cause = cause or (v.reasons[0] if v.reasons else "incomplete evidence")
            out = [f"{headline}: {cause}.", f"comparison: {summary}."]
        else:
            out = [f"{headline}: {summary}."]
    out.append(f"tests: {v.tests} (comparison outcome; unchanged and known failures do not reject)")
    out.append(f"base {b.get('core_rev') or '?'}: {b.get('tests', '?')} tests; "
               f"candidate {c.get('core_rev') or '?'}: {c.get('tests', '?')} tests")
    for r in v.reasons:
        out.append(f"  reason: {r}")

    def section(title, items, fmt):
        if items:
            out.append(f"{title} ({len(items)}):")
            out.extend("  " + fmt(i) for i in items[:50])
            if len(items) > 50:
                out.append(f"  ... {len(items) - 50} more")

    loc = lambda i: f"{i['suite']}/{i['config']}/{i['id']}"
    section("new failures", v.new_failures,
            lambda i: f"{loc(i)}  {i['signature']}  seed {i.get('seed')}  (base: {i.get('base')})  {i.get('run') or ''}")
    section("inconclusive (prove nothing; rerun)", v.inconclusive,
            lambda i: f"{loc(i)}  {i.get('signature') or ''}" + (f"  seed {i['seed']}" if i.get("seed") is not None else "")
            + f"  ({i['why']})  {i.get('run') or ''}")
    section("missing", v.missing, lambda i: f"{loc(i)}" + (f"  seed {i['seed']}" if "seed" in i else "")
            + (f"  seeds {i['seeds']['candidate']} < {i['seeds']['base']}" if "seeds" in i else "")
            + f"  (base: {i['base_status']})")
    section("fixed", v.fixed, lambda i: f"{loc(i)}  was {i['signature']}")
    section("known failures", v.known_failures, lambda i: f"{loc(i)}  {i['signature']}  ({i.get('reason')})")
    section("still failing (same signature as base)", v.extra.get("still_failing", []),
            lambda i: f"{loc(i)}  {i['signature']}")
    regress = [p for p in v.perf if p["regression"]]
    section("perf regressions", regress,
            lambda p: f"{loc(p)}  {p['metric']} {p['base']} -> {p['candidate']} ({p['change']:+.2%})")
    if v.perf and not regress:
        worst = max(v.perf, key=lambda p: p["change"])
        out.append(f"perf: {len(v.perf)} compared, worst {worst['id']} {worst['metric']} {worst['change']:+.2%}")
    return "\n".join(out)
