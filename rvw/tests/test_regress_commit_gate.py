"""C8: only committed source identities can earn an accept."""
import json

import pytest

from rvw.mcp.envelope import envelope
from rvw.mcp.registry import Registry
from rvw.regress.compare import compare
from rvw.regress.source import describe
from rvw.results import SuiteResults, TestEntry, find_results
from regress_fixtures import git


def _suite(source, status="pass"):
    return SuiteResults("run", "isa", "fake", "small", "now", source=source, tests=[
        TestEntry("test", status, seed=1, signature="fail:7" if status == "fail" else None,
                  extra={"elf_sha256": "a" * 64, "options": {}})])


COMMITTED = {"core_rev_full": "a" * 40, "core_dirty": False}


@pytest.mark.parametrize("side", ["base", "candidate"])
@pytest.mark.parametrize("source", [
    {**COMMITTED, "core_dirty": True, "core_fingerprint": "b" * 64},
    {"core_rev": "aaaaaaa", "core_dirty": False},
    {"core_rev_full": "a" * 40},
    {"core_dirty": False},
    {},
])
def test_compare_requires_recorded_committed_identity(side, source):
    base, candidate = _suite(COMMITTED), _suite(COMMITTED)
    (base if side == "base" else candidate).source = source
    verdict = compare([base], [candidate])
    assert verdict.verdict == "inconclusive"
    assert verdict.extra["inconclusive_cause"] == "candidate_not_committed"
    assert verdict.extra["hint"] == "commit (a scratch branch is fine) and rerun"
    assert side in " ".join(verdict.reasons)


def test_compare_committed_unchanged_failure_still_accepts():
    verdict = compare([_suite(COMMITTED, "fail")], [_suite(COMMITTED, "fail")])
    assert verdict.verdict == "accept"
    assert verdict.extra["still_failing"]


def _mcp(action, **arguments):
    registry, problems = Registry.discover({"regress"})
    assert not problems
    try:
        _, data, error = registry.call_json("regress_" + action, arguments)
        assert not error, data
        if "job_id" in data:
            _, status, error = registry.call_json("job_status", {"job_id": data["job_id"], "wait_s": 60})
            assert not error and status["status"] == "done", status
            data = status["result"]
        return data
    finally:
        registry.jobs.shutdown()


def _gate(fake, rvw, transport, base, **options):
    if transport == "mcp":
        return _mcp("gate", core=str(fake.config), base_rev=base, no_cache=True, **options)
    args = []
    for key, value in options.items():
        args.extend(("--" + key.replace("_", "-"), str(value)))
    code, out, data = rvw("regress", "gate", "--core", fake.config, "--base-rev", base,
                          "--no-cache", *args, "--json")
    assert code == {"accept": 0, "reject": 1, "inconclusive": 3}[data["verdict"]], out
    return data


@pytest.mark.parametrize("transport", ["cli", "mcp"])
@pytest.mark.parametrize("failure", [False, True])
def test_dirty_default_candidate_never_accepts(fake, rvw, transport, failure):
    base = describe(fake.repo).rev
    (fake.repo / "overrides.json").write_text(json.dumps(
        {"rv64ui-p-add": "status=fail fail_code=7"} if failure else {}))
    verdict = _gate(fake, rvw, transport, base)
    assert verdict["verdict"] == ("reject" if failure else "inconclusive")
    assert verdict["schema"] == "rvw.verdict/2"
    assert verdict["tests"] == ("fail" if failure else "pass")
    assert verdict.get("not_accepted_reason") == (None if failure else "uncommitted")
    assert verdict["inconclusive_cause"] == "candidate_not_committed"
    assert verdict["hint"] == "commit (a scratch branch is fine) and rerun"
    assert verdict["compared"] == 2
    results = find_results(verdict["gate"]["candidate"]["path"])
    assert results[0].source["core_dirty"] is True
    assert results[0].tests


@pytest.mark.parametrize("transport", ["cli", "mcp"])
def test_clean_default_candidate_runs_from_commit_checkout(fake, rvw, transport):
    base = describe(fake.repo).rev
    verdict = _gate(fake, rvw, transport, base)
    assert verdict["verdict"] == "accept"
    assert verdict["tests"] == "pass"
    candidate = find_results(verdict["gate"]["candidate"]["path"])[0]
    explicit = _gate(fake, rvw, transport, base, cand_rev=base)
    recorded = find_results(explicit["gate"]["candidate"]["path"])[0]
    assert candidate.source == recorded.source
    assert candidate.source["core_repo"] != str(fake.repo)
    assert candidate.source["core_rev_full"] == base
    assert candidate.source["core_dirty"] is False


def test_staged_edit_with_head_bytes_stays_uncommitted(fake, rvw):
    base = describe(fake.repo).rev
    path = fake.repo / "counter"
    original = path.read_bytes()
    path.write_text("staged change")
    git(fake.repo, "add", "counter")
    path.write_bytes(original)
    assert describe(fake.repo).dirty
    verdict = _gate(fake, rvw, "cli", base)
    assert verdict["verdict"] == "inconclusive"
    assert verdict["inconclusive_cause"] == "candidate_not_committed"


@pytest.mark.parametrize("side", ["base", "candidate"])
def test_stored_live_tree_cli_mcp_parity(fake, rvw, tmp_path, side):
    base, candidate = tmp_path / "base", tmp_path / "candidate"
    for name, output in (("base", base), ("candidate", candidate)):
        dirty = fake.repo / "uncommitted.txt"
        if name == side:
            dirty.write_text("local edit")
        else:
            dirty.unlink(missing_ok=True)
        assert rvw("regress", "run", "--core", fake.config, "--tier", "quick", "--out", output)[0] == 0
    for action in ("compare", "gate"):
        args = ["--base", base, "--cand", candidate] if action == "gate" else [base, candidate]
        code, _, cli = rvw("regress", action, *args, "--core", fake.config, "--json")
        arguments = {"base": str(base), "cand" if action == "gate" else "candidate": str(candidate)}
        mcp = _mcp(action, core=str(fake.config), **arguments)
        assert code == 3 and cli["verdict"] == "inconclusive"
        assert cli["inconclusive_cause"] == "candidate_not_committed"
        assert (envelope(cli) if action == "compare" else cli) == mcp
