"""Delta signs, fixed calibration and paired evidence identity."""
import json
import pytest
from rvw.ooo.delta import delta, delta_error

pytestmark = pytest.mark.fast


def test_delta_error():
    assert delta_error(-.1, -.14)["wrong_delta"] is False
    assert delta_error(-.1, -.16)["wrong_delta"] is True
    assert delta_error(.1, -.1)["sign_match"] is False
    assert delta_error(0, 0)["relative_error"] is None
    assert delta_error(0, .01)["wrong_delta"] is True


def make_plan(tmp_path):
    from test_ooo_evidence import inputs
    from rvw.ooo.evidence import calibrate
    cp, data = inputs(tmp_path)
    calibrate(cp, tmp_path/"calibration")
    row = data["samples"][0]
    variant = dict(row, c1="variant-c1")
    c1 = json.loads((tmp_path/row["c1"]).read_text())
    c1["cycles"] *= 2
    (tmp_path/"variant-c1").write_text(json.dumps(c1))
    spec = dict(schema="rvw.ooo-delta-plan/1", config="config", calibration="calibration",
                variants=[dict(id="rob", changes={"rob_entries": 16})],
                samples=[dict(id="program", base=row, variants={"rob": variant})])
    p = tmp_path/"delta-plan"
    p.write_text(json.dumps(spec))
    return p, spec


def test_fixed_base_and_zero_model_delta(tmp_path):
    p, _ = make_plan(tmp_path)
    r = delta(p, tmp_path/"result")
    assert r["rows"][0]["measured_delta"] == -.5
    assert r["rows"][0]["predicted_delta"] == 0
    assert r["summary"]["wrong_deltas"] == 1


@pytest.mark.parametrize("change", ["seed", "config", "two", "empty"])
def test_reject_unpaired_or_unfrozen(tmp_path, change):
    p, spec = make_plan(tmp_path)
    if change == "seed":
        c1 = tmp_path/"variant-c1"
        row = json.loads(c1.read_text()); row["seed"] = 17
        c1.write_text(json.dumps(row))
    elif change == "config":
        spec["config"] = "variant-c1"
    elif change == "two":
        spec["variants"][0]["changes"]["issue_entries"] = 8
    else:
        spec["samples"] = []
    p.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        delta(p, tmp_path/"result")


def test_reuse_frozen_base_after_current_engine_check(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module("rvw.ooo.delta")
    p, spec = make_plan(tmp_path)
    second = dict(spec["samples"][0], id="same-capture-again")
    spec["samples"].append(second)
    p.write_text(json.dumps(spec))
    actual, calls = module.run, []
    def record(*args, **kw):
        calls.append(args)
        return actual(*args, **kw)
    monkeypatch.setattr(module, "run", record)
    result = delta(p, tmp_path/"result")
    assert len(result["rows"]) == 2
    assert len(calls) == 1
