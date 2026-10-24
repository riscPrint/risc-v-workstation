"""A stable test name does not identify its program or stimulus."""
import hashlib

import pytest

from rvw.regress.compare import compare
from rvw.regress.config import load_config
from rvw.regress.known import Known
from rvw.regress.plan import suites_plan
from rvw.regress.runner import RunOptions, Runner
from rvw.regress.source import describe
from rvw.results import SuiteResults, TestEntry, find_results


def _suite(status="fail", seed=1):
    return SuiteResults("run", "isa", "fake", "small", "now",
                        source={"core_rev_full": "a" * 40, "core_dirty": False}, tests=[
        TestEntry("test", status, seed=seed, signature="fail:7" if status == "fail" else None,
                  extra={"elf_sha256": "a" * 64, "options": {"max_cycles": 1000}})])


@pytest.mark.parametrize("field,value", [("elf_sha256", "b" * 64), ("elf_sha256", None),
                                         ("options", {"max_cycles": 2000}), ("options", None),
                                         ("options", {"max_cycles": True})])
@pytest.mark.parametrize("status", ["fail", "pass"])
@pytest.mark.parametrize("known", [False, True])
def test_changed_or_missing_inputs_are_incomparable(field, value, status, known):
    base, cand = _suite(), _suite(status)
    cand.tests[0].extra[field] = value
    v = compare([base], [cand], [Known("isa", "test", "fail:7", "old bug")] if known else [])
    assert v.verdict == "inconclusive"
    assert not v.fixed and not v.extra["still_failing"] and not v.known_failures
    assert v.inconclusive and "input" in v.inconclusive[0]["why"]
    assert v.extra["compared"] == 0


@pytest.mark.parametrize("policy", ["auto", "count"])
def test_random_seed_changes_cannot_cover_baseline_failure(policy):
    base, cand = _suite(seed=1), _suite(seed=2)
    base.extra = cand.extra = {"seeds": {"mode": "random"}}
    v = compare([base], [cand], seed_policy=policy)
    assert v.verdict == "inconclusive" and not v.extra["still_failing"] and not v.fixed


def test_failure_signature_cannot_move_between_seeds():
    base, cand = _suite("pass", seed=1), _suite("fail", seed=1)
    base.tests.append(_suite("fail", seed=2).tests[0])
    cand.tests.append(_suite("pass", seed=2).tests[0])
    v = compare([base], [cand])
    assert v.verdict == "reject" and v.new_failures[0]["seed"] == 1
    assert not v.extra["still_failing"]


def test_same_signature_on_old_failing_seed_cannot_hide_new_failing_seed():
    base, cand = _suite("fail", seed=1), _suite("fail", seed=1)
    base.tests.append(_suite("pass", seed=2).tests[0])
    cand.tests.append(_suite("fail", seed=2).tests[0])
    v = compare([base], [cand])
    assert v.verdict == "reject" and v.new_failures[0]["seed"] == 2


def test_equal_inputs_still_compare_and_fix():
    assert compare([_suite()], [_suite()]).verdict == "accept"
    assert compare([_suite()], [_suite("pass")]).fixed


def test_legacy_entries_without_identity_cannot_accept():
    base, cand = _suite(), _suite()
    base.tests[0].extra = cand.tests[0].extra = {}
    assert compare([base], [cand]).verdict == "inconclusive"


def test_missing_seed_on_both_sides_is_not_comparable():
    assert compare([_suite(seed=None)], [_suite(seed=None)]).verdict == "inconclusive"


def test_changed_inputs_do_not_compare_performance():
    base, cand = _suite("pass"), _suite("pass")
    base.tests[0].cycles = 100
    cand.tests[0].cycles = 1
    cand.tests[0].extra["elf_sha256"] = "b" * 64
    base.extra = cand.extra = {"perf_metrics": ["cycles"]}
    v = compare([base], [cand])
    assert v.verdict == "inconclusive" and not v.perf


def test_runner_keeps_program_and_stimulus_in_c3(fake, tmp_path):
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / "run", RunOptions(log=None, index=False))
    runner.run(suites_plan(core, ["isa"], None))
    suite = find_results(runner.out)[0]
    for test in suite.tests:
        assert test.extra["elf_sha256"] == hashlib.sha256((fake.isa / test.id).read_bytes()).hexdigest()
        assert test.extra["options"] == {"max_cycles": 1000, "mem_latency": None}
        assert test.seed == 1


def test_adapter_default_stimulus_changes_are_incomparable(fake, tmp_path, monkeypatch):
    core = load_config(str(fake.config))
    core.suite("isa").max_cycles = None
    suites = []
    for limit in (1000, 2000):
        runner = Runner(core, describe(fake.repo), tmp_path / str(limit),
                        RunOptions(log=None, index=False, use_cache=False))
        actual = runner._run_tests
        def run(*args):
            actual(*args)
            from rvw.results import load_run, save_run
            for path in runner.out.rglob("result.json"):
                r = load_run(path)
                r.max_cycles = limit
                save_run(r, path)
        monkeypatch.setattr(runner, "_run_tests", run)
        assert runner.run(suites_plan(core, ["isa"], None))["ok"]
        suites.append(find_results(runner.out))
    assert compare(*suites).verdict == "inconclusive"


def test_build_flags_are_part_of_input_identity():
    base, cand = _suite(), _suite("pass")
    for suite in (base, cand):
        suite.tests[0].extra.update(kind="build", elf_sha256=None, build_options=[])
    assert compare([base], [cand]).fixed
    cand.tests[0].extra["build_options"] = ["--other"]
    v = compare([base], [cand])
    assert v.verdict == "inconclusive" and not v.fixed


@pytest.mark.parametrize("reader", ["compare", "gate", "mcp"])
def test_rebuilt_elf_never_counts_as_still_failing(fake, rvw, tmp_path, reader):
    fake.prog("rv64ui-p-add", "status=fail fail_code=7")
    for side in ("base", "cand"):
        if side == "cand":
            fake.prog("rv64ui-p-add", "status=pass")
            fake.commit({"rv64ui-p-add": "status=fail fail_code=7"}, msg="broken")
        code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out",
                         tmp_path / side, "--no-cache", "--no-index", "--json")
        assert code == 1
    base, cand = tmp_path / "base", tmp_path / "cand"
    if reader == "mcp":
        from rvw.mcp.registry import Registry
        registry, errors = Registry.discover({"regress"})
        assert not errors
        _, v, error = registry.call_json("regress_compare", {"base": str(base), "candidate": str(cand)})
        assert not error
    else:
        args = (base, cand) if reader == "compare" else ("--core", fake.config, "--base", base, "--cand", cand)
        code, _, v = rvw("regress", reader, *args, "--json")
        assert code == 3
    assert v["verdict"] == "inconclusive" and not v["still_failing"]
