"""C4 separates comparison evidence from committed-source acceptance."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from regress_fixtures import git
from rvw.regress.compare import compare, format_verdict
from rvw.regress.plan import gate
from rvw.regress.runner import Runner
from rvw.regress.source import describe
from rvw.results import SchemaError, Verdict, find_results, load_run
from test_regress_adapter_capture import prepared, RTL
from test_regress_commit_gate import COMMITTED, _suite


@pytest.mark.parametrize("side", ["base", "candidate"])
def test_dirty_pass_headline_names_the_uncommitted_side(side):
    base, cand = _suite(COMMITTED, "fail"), _suite(COMMITTED, "fail")
    (base if side == "base" else cand).source = {**COMMITTED, "core_dirty": True}
    v = compare([base], [cand])
    assert v.tests == "pass" and v.not_accepted_reason == "uncommitted"
    assert v.exit_code == 3 and not v.accepted
    lines = format_verdict(v).splitlines()
    assert lines[0] == "TESTS PASS: 1 compared, 0 new failures, 1 still failing (test)."
    assert lines[1].startswith(f"NOT ACCEPTED: the {side}")
    assert "Commit (a scratch branch is fine) and rerun" in lines[1]
    assert Verdict.from_dict(v.to_dict()) == v


@pytest.mark.parametrize("status,tests,headline", [("fail", "fail", "REJECT:"),
                                                    ("error", "incomplete", "INCONCLUSIVE:")])
def test_dirty_failure_or_incomplete_never_gets_tests_pass(status, tests, headline):
    v = compare([_suite(COMMITTED)], [_suite({**COMMITTED, "core_dirty": True}, status)])
    assert v.tests == tests
    assert format_verdict(v).startswith(headline)
    assert "TESTS PASS" not in format_verdict(v)


def test_schema_requires_test_outcome_and_refuses_old_verdicts():
    v = compare([_suite(COMMITTED)], [_suite(COMMITTED)]).to_dict()
    assert v["schema"] == "rvw.verdict/2" and v["tests"] == "pass"
    for change in ({"schema": "rvw.verdict/1"}, {"tests": None}, {"tests": "fail"},
                   {"not_accepted_reason": "uncommitted"}):
        with pytest.raises(SchemaError):
            Verdict.from_dict({**v, **change})


def rtl_core(fake, tmp_path, **kwargs):
    first, plan = prepared(fake, tmp_path, c1_tools_dirty=False,
        corrupt="document['result_claims'].update({'source.tools_dirty': False, 'source.tools_rev': 'a' * 40})",
        **kwargs)
    first.close()
    adapter = first.core.adapter[1]
    path = Path(adapter)
    path.write_text(path.read_text().replace('"tools_dirty": False', '"tools_dirty": False, "tools_rev": "a" * 40'))
    return first, plan


def test_dirty_then_commit_gate_reuses_same_rtl_without_simulation(fake, tmp_path):
    first, _ = rtl_core(fake, tmp_path)
    base = describe(fake.repo).rev
    (fake.repo / "note.txt").write_text("harmless core note\n")
    def run():
        return gate(first.core, "quick", base, None, None, None, None, first.opts, None, None)["verdict"]
    dirty = run()
    assert dirty.tests == "pass" and dirty.not_accepted_reason == "uncommitted"
    count = len(fake.calls("run"))
    git(fake.repo, "add", "note.txt")
    git(fake.repo, "commit", "-qm", "core note")
    committed = run()
    assert committed.verdict == "accept" and committed.tests == "pass"
    assert len(fake.calls("run")) == count
    candidate = find_results(committed.extra["gate"]["candidate"]["path"])[0]
    assert candidate.source["core_rev_full"] == describe(fake.repo).rev
    assert candidate.source["core_dirty"] is False
    assert all(t.extra["cached"] and t.extra["rtl_sha256"] == RTL for t in candidate.tests)
    for t in candidate.tests:
        r = load_run(candidate.path / t.run)
        assert r.source["core_rev_full"] == describe(fake.repo).rev
        assert r.extra["reused_from_source"]["core_rev_full"] == base


def test_dirty_pass_is_cached_before_the_core_commit(fake, tmp_path):
    first, plan = rtl_core(fake, tmp_path)
    (fake.repo / "note.txt").write_text("dirty source")
    dirty = Runner(first.core, describe(fake.repo), tmp_path / "dirty", first.opts)
    assert dirty.run(plan)["ok"]
    count = len(fake.calls("run"))
    git(fake.repo, "add", "note.txt")
    git(fake.repo, "commit", "-qm", "core note")
    committed = Runner(first.core, describe(fake.repo), tmp_path / "committed", first.opts)
    assert committed.run(plan)["ok"]
    assert len(fake.calls("run")) == count
    for suite in find_results(committed.out):
        for t in suite.tests:
            assert t.extra["cached"]
            assert load_run(suite.path / t.run).extra["reused_from_source"]["core_dirty"] is True


def test_other_inconclusive_causes_remain_visible_with_dirty_source(fake, tmp_path):
    first, plan = rtl_core(fake, tmp_path)
    (fake.repo / "note.txt").write_text("dirty source")
    stored = Runner(first.core, describe(fake.repo), tmp_path / "stored", first.opts)
    assert stored.run(plan)["ok"]
    first.opts.max_cycles = 999
    v = gate(first.core, "quick", None, None, str(stored.out), str(stored.out),
             None, first.opts, None, None)["verdict"]
    assert v.tests == "incomplete" and v.verdict == "inconclusive"
    assert v.extra["inconclusive_cause"] == "stored_plan_incomplete"
    assert format_verdict(v).startswith("INCONCLUSIVE:")
    assert "stored_plan_incomplete" in format_verdict(v)


@pytest.mark.parametrize("changed", ["rtl", "elf", "options", "dependency", "native", "harness"])
def test_dirty_rtl_reuse_keeps_all_other_inputs(fake, tmp_path, changed):
    model = tmp_path / "model.json"
    values = {"rtl_sha256": RTL, "native_sha256": "12" * 32}
    model.write_text(json.dumps(values))
    first, plan = rtl_core(fake, tmp_path, model_file=model)
    policy = tmp_path / "policy"
    policy.write_text("first")
    first.core.cache_paths.append(policy)
    (fake.repo / "note.txt").write_text("dirty")
    initial = Runner(first.core, describe(fake.repo), tmp_path / "dirty", first.opts)
    assert initial.run(plan)["ok"]
    count = len(fake.calls("run"))
    if changed in ("rtl", "native"):
        values["rtl_sha256" if changed == "rtl" else "native_sha256"] = "ef" * 32
        model.write_text(json.dumps(values))
    elif changed == "elf":
        fake.prog("rv64ui-p-add", "cycles=103")
    elif changed == "options":
        plan[0].suite.max_cycles += 1
    elif changed == "dependency":
        policy.write_text("second")
    else:
        adapter = Path(first.core.adapter[1])
        adapter.write_text(adapter.read_text() + "\n# changed harness\n")
    again = Runner(first.core, describe(fake.repo), tmp_path / "changed", first.opts)
    assert again.run(plan)["ok"]
    assert len(fake.calls("run")) > count


def test_complete_rtl_failure_reuse_preserves_reject(fake, tmp_path):
    first, plan = rtl_core(fake, tmp_path)
    fake.prog("rv64ui-p-add", "status=fail fail_code=7")
    (fake.repo / "note.txt").write_text("dirty source")
    dirty = Runner(first.core, describe(fake.repo), tmp_path / "dirty", first.opts)
    summary = dirty.run(plan)
    assert not summary["ok"] and summary["inconclusive"] == 0
    count = len(fake.calls("run"))
    git(fake.repo, "add", "note.txt")
    git(fake.repo, "commit", "-qm", "core note")
    committed = Runner(first.core, describe(fake.repo), tmp_path / "committed", first.opts)
    assert not committed.run(plan)["ok"]
    assert len(fake.calls("run")) == count
    candidate = find_results(committed.out)[0]
    assert all(t.extra["cached"] for t in candidate.tests)
    # A cached hardware failure remains rejecting evidence against a passing baseline.
    base = replace(candidate, tests=[replace(t, status="pass", signature=None) for t in candidate.tests])
    verdict = compare([base], [candidate])
    assert verdict.verdict == "reject" and verdict.tests == "fail" and verdict.exit_code == 1
    assert verdict.new_failures[0]["signature"] == "fail:7"


def test_complete_rtl_inconclusive_result_is_not_cached(fake, tmp_path):
    first, plan = rtl_core(fake, tmp_path)
    fake.prog("rv64ui-p-add", "status=error")
    (fake.repo / "note.txt").write_text("dirty source")
    initial = Runner(first.core, describe(fake.repo), tmp_path / "initial", first.opts)
    assert initial.run(plan)["inconclusive"] == 1
    count = len(fake.calls("run"))
    again = Runner(first.core, describe(fake.repo), tmp_path / "again", first.opts)
    assert again.run(plan)["inconclusive"] == 1
    assert len(fake.calls("run")) == count + 1


def test_dirty_harness_error_is_the_headline():
    v = compare([_suite(COMMITTED)], [_suite({**COMMITTED, "core_dirty": True}, "error")])
    line = format_verdict(v).splitlines()[0]
    assert line.startswith("INCONCLUSIVE: 1 inconclusive result")
    assert "candidate_not_committed" not in line
