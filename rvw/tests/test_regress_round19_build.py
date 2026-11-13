"""Build arguments and returned identities cannot change the selected configuration."""
from regress_fixtures import legacy_layout
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rvw.regress.config import ConfigError, Suite, load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import JOB_FILE, RunOptions, Runner
from rvw.regress.source import describe
from rvw.results import find_results, load_run, save_run

HERE = Path(__file__).resolve().parent


@pytest.mark.parametrize("flag", ["--config", "--json", "--rvfi"])
@pytest.mark.parametrize("equals", [False, True])
def test_reserved_build_arguments(flag, equals):
    args = [f"{flag}=small"] if equals else [flag, "small"]
    with pytest.raises(ConfigError, match="reserved"):
        Suite("elab", kind="build", build_options=args)


def test_custom_build_arguments_remain_available():
    Suite("elab", kind="build", build_options=["--wave", "--coverage", "--konata"])


@pytest.mark.parametrize("args", [["--config", "small"], ["--config=small"]])
def test_build_override_is_refused_before_adapter(fake, rvw, tmp_path, args):
    fake.config.write_text(fake.config.read_text().replace('kind = "build"',
                           'kind = "build"\nbuild_options = ' + json.dumps(args)))
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "elab",
                        "--config", "large", "--out", tmp_path / "run", "--json")
    assert code == 2 and data is None
    assert "reserved" in rvw.stderr
    assert not fake.calls()
    assert not list((tmp_path / "run").rglob("junit.xml"))


def test_mutated_build_arguments_are_checked(fake, tmp_path):
    core = load_config(str(fake.config))
    core.suite("elab").build_options = ["--config", "small"]
    with pytest.raises(ConfigError, match="reserved"):
        runner = Runner(core, describe(fake.repo), tmp_path / "run", RunOptions(log=None))
        runner.run(suites_plan(core, ["elab"], ["large"]))
    assert not fake.calls()


def _build_adapter(fake, tmp_path, payload):
    adapter = tmp_path / "build_adapter.py"
    adapter.write_text((HERE / "fake_adapter.py").read_text().replace(
        '{"config": a.config, "status": "ok"}', repr(payload)))
    core = load_config(str(fake.config))
    core.adapter[1] = str(adapter)
    return core


@pytest.mark.parametrize("payload", [
    {"config": "small"},
    {"config": None},
    {"models": [{"model": {"config": "small"}}]},
    {"config": "large", "models": [{"model": {"config": "small"}}]},
    {"models": [{"model": {"config": "large"}}, {"model": {"config": "small"}}]},
    {"models": []},
    {"models": [{"model": {}}]},
    {"models": "large"},
    {"core": "other", "config": "large"},
])
def test_reported_build_config_must_match_in_c1_c3_and_junit(fake, tmp_path, payload):
    core = _build_adapter(fake, tmp_path, payload)
    out = tmp_path / "run"
    runner = Runner(core, describe(fake.repo), out, RunOptions(log=None, index=False))
    summary = runner.run(suites_plan(core, ["elab"], ["large"]))
    assert not summary["ok"] and summary["inconclusive"] == 1
    res = find_results(out)[0]
    assert not res.tests[0].conclusive
    run = load_run(res.path / res.tests[0].run)
    assert run.why_inconclusive and "build" in (run.message or run.why_inconclusive)
    assert run.extra["build"] == payload
    assert len(ET.parse(res.path / "junit.xml").findall(".//error")) == 1
    assert not list(runner.cache.dir.rglob(JOB_FILE))


@pytest.mark.parametrize("payload", [
    {"config": "large"},
    {"schema": "rvw.build/1", "core": "fake", "models": [{"model": {"config": "large"}}]},
    {"status": "ok"},  # Older adapters can report exit status without build identity.
])
def test_matching_or_unreported_build_config(fake, tmp_path, payload):
    core = _build_adapter(fake, tmp_path, payload)
    runner = Runner(core, describe(fake.repo), tmp_path / "run", RunOptions(log=None, index=False))
    assert runner.run(suites_plan(core, ["elab"], ["large"]))["ok"]


def test_conflicting_saved_build_cannot_resume(fake, tmp_path):
    core = load_config(str(fake.config))
    out = tmp_path / "run"
    opts = RunOptions(log=None, index=False)
    plan = suites_plan(core, ["elab"], ["large"])
    assert Runner(core, describe(fake.repo), out, opts).run(plan)["ok"]
    legacy_layout(out)
    res = find_results(out)[0]
    path = res.path / res.tests[0].run
    run = load_run(path)
    run.extra["build"]["config"] = "small"
    save_run(run, path)
    fake.reset_calls()
    assert Runner(core, describe(fake.repo), out, opts).run(plan)["ok"]
    assert len(fake.calls("build")) == 1
    assert load_run(path).extra["build"]["config"] == "large"


def test_old_unchecked_build_job_runs_again(fake, tmp_path, monkeypatch):
    core = load_config(str(fake.config))
    out = tmp_path / "run"
    opts = RunOptions(log=None, index=False)
    plan = suites_plan(core, ["elab"], ["large"])
    assert Runner(core, describe(fake.repo), out, opts).run(plan)["ok"]
    legacy_layout(out)
    job_file = next(out.rglob(JOB_FILE))
    meta = json.loads(job_file.read_text())
    meta["params"]["runner_identity_version"] = 5
    job_file.write_text(json.dumps(meta))
    fake.reset_calls()
    monkeypatch.setenv("FAKE_BUILD_FAIL", "1")
    assert not Runner(core, describe(fake.repo), out, opts).run(plan)["ok"]
    assert len(fake.calls("build")) == 1


def test_runner_rvfi_flag_applies_to_build_suite(fake, tmp_path, monkeypatch):
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / "run",
                    RunOptions(log=None, index=False, rvfi_trace=True))
    proc = runner._proc
    calls = []

    def record(cmd, *args, **kwargs):
        calls.append(cmd)
        return proc(cmd, *args, **kwargs)

    monkeypatch.setattr(runner, "_proc", record)
    assert runner.run(suites_plan(core, ["elab"], ["large"]))["ok"]
    assert len(calls) == 1 and calls[0][-1] == "--rvfi"
