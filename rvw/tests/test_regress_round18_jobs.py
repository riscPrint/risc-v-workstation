"""Suite options and adapter results cannot replace the requested job identity."""
from regress_fixtures import legacy_layout
import xml.etree.ElementTree as ET

import pytest

from rvw.regress.config import ConfigError, Suite, load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import JOB_FILE, RunOptions, Runner
from rvw.regress.source import describe
from rvw.results import find_results, load_run, save_run


@pytest.mark.parametrize("key", ["config", "elf", "out", "seed", "max_cycles", "max-cycles",
                                "mem_latency", "mem-latency", "rvfi_trace", "rvfi-trace",
                                "wall_timeout", "wall-timeout", "--config", "--elf", "--out",
                                "--seed", "--max-cycles", "--mem-latency", "--rvfi-trace",
                                "--wall-timeout"])
def test_suite_refuses_reserved_job_options(key):
    with pytest.raises(ConfigError, match="reserved"):
        Suite("isa", options={key: 1})


def test_mutated_suite_cannot_override_config(fake, tmp_path):
    core = load_config(str(fake.config))
    core.suite("isa").options["config"] = "small"
    with pytest.raises(ConfigError, match="reserved"):
        runner = Runner(core, describe(fake.repo), tmp_path / "run", RunOptions(log=None))
        runner.run(suites_plan(core, ["isa"], ["large"]))
    assert not fake.calls()


@pytest.mark.parametrize("field,value", [("config", "large"), ("core", "other"),
                                         ("elf_sha256", "0" * 64), ("elf_sha256", None),
                                         ("seed", 7), ("seed", None), ("max_cycles", 123),
                                         ("options", {"max_cycles": 123})])
@pytest.mark.parametrize("reuse", ["fresh", "resume", "cache"])
def test_conflicting_c1_job_identity_never_passes(fake, tmp_path, monkeypatch, field, value, reuse):
    core = load_config(str(fake.config))
    src = describe(fake.repo)
    out = tmp_path / "run"
    opts = RunOptions(log=None, index=False, use_cache=reuse != "resume")
    runner = Runner(core, src, out, opts)
    plan = suites_plan(core, ["isa"], None)

    def poison(path):
        r = load_run(path)
        if field == "options":
            r.extra[field] = value
        else:
            setattr(r, field, value)
        save_run(r, path)

    if reuse == "fresh":
        actual = runner._run_tests
        def run(*args):
            actual(*args)
            for path in out.rglob("result.json"):
                poison(path.parent)
        monkeypatch.setattr(runner, "_run_tests", run)
    else:
        assert runner.run(plan)["ok"]
        legacy_layout(out)
        for pointer in list(runner.cache.dir.rglob("current")) if runner.cache else []:
            legacy_layout(pointer.parent)
        root = out if reuse == "resume" else runner.cache.dir
        for path in root.rglob("result.json"):
            poison(path.parent)
        if reuse == "cache":
            out = tmp_path / "restored"
        runner = Runner(core, src, out, opts)
        fake.reset_calls()
    summary = runner.run(plan)
    results = find_results(out)
    if reuse == "fresh":
        assert not summary["ok"] and summary["inconclusive"] == 3
        assert all(not t.conclusive for res in results for t in res.tests)
        assert all(load_run(res.path / t.run).why_inconclusive for res in results for t in res.tests)
        assert not list(runner.cache.dir.rglob(JOB_FILE))
        assert len(ET.parse(results[0].path / "junit.xml").findall(".//error")) == 3
    else:
        assert summary["ok"]
        assert len(fake.calls("run")) == 3


def test_unreported_custom_option_is_inconclusive(fake, tmp_path):
    core = load_config(str(fake.config))
    core.suite("isa").options = {"custom": "stimulus"}
    runner = Runner(core, describe(fake.repo), tmp_path / "run", RunOptions(log=None, index=False))
    result = runner.run(suites_plan(core, ["isa"], None))
    assert not result["ok"] and result["inconclusive"] == 3


def test_matching_custom_option_is_checked(fake, tmp_path, monkeypatch):
    core = load_config(str(fake.config))
    core.suite("isa").options = {"custom-mode": "stimulus"}
    runner = Runner(core, describe(fake.repo), tmp_path / "run", RunOptions(log=None, index=False))
    actual = runner._run_tests
    def run(*args):
        actual(*args)
        for path in runner.out.rglob("result.json"):
            r = load_run(path)
            r.extra["options"] = {"custom_mode": "stimulus", "max_cycles": 1000}
            save_run(r, path)
    monkeypatch.setattr(runner, "_run_tests", run)
    assert runner.run(suites_plan(core, ["isa"], None))["ok"]


def test_preview_does_not_offer_conflicting_cached_jobs(fake, tmp_path):
    core = load_config(str(fake.config))
    src = describe(fake.repo)
    runner = Runner(core, src, tmp_path / "run", RunOptions(log=None, index=False))
    plan = suites_plan(core, ["isa"], None)
    assert runner.run(plan)["ok"]
    for pointer in list(runner.cache.dir.rglob("current")):
        legacy_layout(pointer.parent)
    for path in runner.cache.dir.rglob("result.json"):
        r = load_run(path)
        r.elf_sha256 = "0" * 64
        save_run(r, path)
    other = Runner(core, src, tmp_path / "preview", RunOptions(log=None, index=False))
    preview = other.preview(plan)
    assert preview["plan"][0]["cached"] == 0 and preview["to_run"] == 3


@pytest.mark.parametrize("evidence", ["both", "replay_only", "artifact_only", "false_flag",
                                       "false_value", "missing_artifact", "outside_artifact", "conflicting_field"])
def test_trace_option_needs_matching_replay_and_artifact(fake, tmp_path, monkeypatch, evidence):
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / "run",
                    RunOptions(log=None, index=False, rvfi_trace=True))
    actual = runner._run_tests
    def run(*args):
        actual(*args)
        for path in runner.out.rglob("result.json"):
            r = load_run(path)
            if evidence not in ("artifact_only", "false_flag", "false_value"):
                r.replay += " --rvfi-trace"
            elif evidence == "false_flag":
                r.replay += " --rvfi-trace=false"
            elif evidence == "false_value":
                r.replay += " --rvfi-trace false"
            if evidence != "replay_only":
                r.artifacts["rvfi_trace"] = "rvfi.jsonl"
                if evidence == "outside_artifact":
                    r.artifacts["rvfi_trace"] = "../outside.jsonl"
                if evidence != "missing_artifact":
                    (path.parent / r.artifacts["rvfi_trace"]).write_text("fixture trace")
            if evidence == "conflicting_field":
                r.extra["rvfi_trace"] = False
            save_run(r, path)
    monkeypatch.setattr(runner, "_run_tests", run)
    summary = runner.run(suites_plan(core, ["isa"], None))
    assert summary["ok"] is (evidence == "both")
    if evidence == "both":
        fake.reset_calls()
        cached = Runner(core, describe(fake.repo), tmp_path / "cached", runner.opts)
        assert cached.run(suites_plan(core, ["isa"], None))["ok"]
        assert not fake.calls("run")
