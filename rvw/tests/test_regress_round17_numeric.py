"""Non-finite thresholds must fail before running jobs or publishing verdicts."""
import pytest

from rvw.regress.compare import compare
from rvw.regress.config import ConfigError, CoreConfig, Suite, load_config
from rvw.regress.plan import gate
from rvw.regress.runner import RunOptions
from rvw.results import SuiteResults, TestEntry, write_json


BAD_TOLERANCES = [float("nan"), float("inf"), -float("inf"), -0.1, True, "nan"]


@pytest.mark.parametrize("value", BAD_TOLERANCES)
def test_compare_rejects_invalid_tolerance_before_reading_results(tmp_path, value):
    with pytest.raises(ValueError, match="perf_tolerance"):
        compare(tmp_path / "missing", tmp_path / "missing", perf_tolerance=value)


@pytest.mark.parametrize("value", BAD_TOLERANCES)
def test_gate_rejects_invalid_tolerance_before_running(fake, tmp_path, value):
    core = load_config(str(fake.config))
    out = tmp_path / "verdict.json"
    with pytest.raises(ValueError, match="perf_tolerance"):
        gate(core, "quick", "HEAD", None, None, None, None, RunOptions(log=None), None, value, out=out)
    assert not fake.calls() and not out.exists()


@pytest.mark.parametrize("json_mode", [True, False])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-0.1"])
def test_cli_invalid_tolerance_writes_no_verdict(fake, rvw, tmp_path, json_mode, value):
    from rvw.results import save_results
    for side in ("base", "cand"):
        res = SuiteResults(side, "bench", "fake", "small", "now",
                           tests=[TestEntry("test", "pass", seed=1, cycles=100)],
                           source={"core_rev": side}, extra={"perf_metrics": ["cycles"]})
        save_results(res, tmp_path / side)
    dest = tmp_path / "verdict.json"
    args = ["regress", "compare", tmp_path / "base", tmp_path / "cand",
            "--out", dest, "--perf-tolerance=" + value]
    if json_mode:
        args.append("--json")
    code, _, _ = rvw(*args)
    assert code == 2 and not dest.exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_strict_atomic_json_preserves_existing_verdict(tmp_path, value):
    dest = tmp_path / "verdict.json"
    dest.write_text("original\n")
    with pytest.raises(ValueError):
        write_json(dest, {"verdict": "accept", "perf_tolerance": value})
    assert dest.read_text() == "original\n"
    assert list(tmp_path.iterdir()) == [dest]


@pytest.mark.parametrize("value", ["nan", "inf", "-0.1"])
def test_toml_rejects_invalid_tolerance(fake, value):
    fake.config.write_text(fake.config.read_text().replace("perf_tolerance = 0.02", "perf_tolerance = " + value))
    with pytest.raises(ConfigError, match="perf_tolerance"):
        load_config(str(fake.config))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 0, -1, True, "1"])
def test_run_options_reject_invalid_timeouts(value):
    with pytest.raises(ConfigError, match="timeout_s"):
        RunOptions(timeout_s=value)


@pytest.mark.parametrize("key", ["identity_timeout_s", "build_timeout_s", "startup_s"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1, True])
def test_core_api_rejects_invalid_timeouts(tmp_path, key, value):
    with pytest.raises(ConfigError, match=key):
        CoreConfig("test", tmp_path / "core.toml", ["adapter"], [], "small", **{key: value})


@pytest.mark.parametrize("key,value", [("timeout_s", float("nan")), ("timeout_s", float("inf")),
                                       ("timeout_s", 0), ("max_cycles", float("nan")),
                                       ("max_cycles", 0), ("mem_latency", -1), ("mem_latency", 1.5)])
def test_suite_api_rejects_invalid_numeric_options(key, value):
    with pytest.raises(ConfigError, match=key):
        Suite("test", **{key: value})


@pytest.mark.parametrize("key", ["identity_timeout_s", "build_timeout_s", "startup_s", "jobs"])
def test_core_toml_rejects_nan(fake, key):
    text = fake.config.read_text()
    lines = [line for line in text.splitlines() if not line.startswith(key + " =")]
    fake.config.write_text("\n".join(lines).replace('[core]', '[core]\n' + key + ' = nan'))
    with pytest.raises(ConfigError, match=key):
        load_config(str(fake.config))


@pytest.mark.parametrize("key", ["timeout_s", "max_cycles", "mem_latency"])
def test_suite_toml_rejects_nan(fake, key):
    text = fake.config.read_text().replace("timeout_s = 20\n", "").replace("max_cycles = 1000\n", "")
    fake.config.write_text(text.replace("[suites.isa]", "[suites.isa]\n" + key + " = nan"))
    with pytest.raises(ConfigError, match=key):
        load_config(str(fake.config))


@pytest.mark.parametrize("key,value", [("jobs", float("nan")), ("max_cycles", float("inf")),
                                       ("seeds", float("nan")), ("seed_base", float("nan"))])
def test_run_options_reject_nonfinite_integer_options(key, value):
    with pytest.raises(ConfigError, match=key):
        RunOptions(**{key: value})


@pytest.mark.parametrize("key", ["max_cycles", "mem_latency", "wall_timeout", "seed"])
def test_suite_manifest_options_reject_nonfinite_numbers(key):
    with pytest.raises(ConfigError, match=key):
        Suite("test", options={key: float("nan")})


def test_nonfinite_custom_manifest_option_is_refused():
    with pytest.raises(ConfigError, match="strict JSON"):
        Suite("test", options={"custom": {"value": float("inf")}})


def test_overflowed_batch_budget_is_refused_before_adapter(fake, tmp_path):
    from rvw.regress.plan import source_for, suites_plan
    from rvw.regress.runner import Runner
    core = load_config(str(fake.config))
    core.startup_s = 1e308
    opts = RunOptions(timeout_s=1e308, log=None)
    r = Runner(core, source_for(core, None), tmp_path / "run", opts)
    with pytest.raises(ConfigError, match="batch timeout"):
        r.run(suites_plan(core, ["isa"], None))
    assert not fake.calls()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_c1_wall_time_must_be_finite_nonnegative(value):
    from rvw.results import validate
    assert any("wall_s" in e for e in validate({"schema": "rvw.run/1", "status": "pass", "wall_s": value}))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 10**1000])
def test_nonfinite_performance_metric_is_inconclusive(value):
    def result(cycles):
        return SuiteResults("run", "bench", "fake", "small", "now",
                            source={"core_rev": "same"}, extra={"perf_metrics": ["cycles"]},
                            tests=[TestEntry("test", "pass", seed=1, cycles=cycles)])
    assert compare([result(100)], [result(value)]).verdict == "inconclusive"
