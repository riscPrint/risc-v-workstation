import json
from dataclasses import asdict
from pathlib import Path

import pytest
from test_ooo import cfg, trace
from rvw.ooo.evidence import calibrate, digest, predict, verify_captures


def inputs(tmp_path):
    config = tmp_path / "config"
    config.write_text(json.dumps(asdict(cfg())))
    mapping = tmp_path / "map"
    mapping.write_text(json.dumps({"issue": dict(model_event="issued", rtl_event="issued",
        edge="rising", unit="instructions", identity="architectural", family="issue", region="whole-program")}))
    samples = []
    for i in range(3):
        elf, tr, c1, ev = [tmp_path / f"{i}-{k}" for k in ("elf", "trace", "c1", "events")]
        elf.write_bytes(bytes([i]))
        trace(tr, step=i+1)
        c1.write_text(json.dumps(dict(schema="rvw.run/1", status="pass", elf="test.elf",
            elf_sha256=digest(elf), core="test", config="tiny", cycles=8+i, instret=4)))
        ev.write_text(json.dumps(dict(c1_sha256=digest(c1), trace_sha256=digest(tr), counts={"issued":4})))
        samples.append(dict(id=str(i), split="training" if i == 0 else "heldout",
            elf=elf.name, trace=tr.name, c1=c1.name, events=ev.name))
    plan = tmp_path / "plan"
    data = dict(schema="rvw.ooo-calibration-plan/1", config=config.name, event_map=mapping.name, samples=samples)
    plan.write_text(json.dumps(data))
    return plan, data


def test_calibration_and_exclusive_prediction(tmp_path):
    p, data = inputs(tmp_path)
    out = tmp_path / "calibration"
    result = calibrate(p, out)
    assert result["accuracy_status"] == "inconclusive"
    assert not result["budgets"]["sufficient_coverage"]
    assert result["correlations"]["issue"]["pearson_r"] is None
    assert result["samples"]["heldout"][0]["events"]["issue"]["error_percent"] == 0
    pred = tmp_path / "prediction"
    assert predict(out, tmp_path / "config", tmp_path / "1-trace", pred)["status"] == "predicted"
    with pytest.raises(FileExistsError):
        predict(out, tmp_path / "config", tmp_path / "1-trace", pred)
    (tmp_path / "0-elf").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        verify_captures(result)


@pytest.mark.parametrize("change", ["elf_overlap", "trace_overlap", "elf_identity", "config_identity", "inconclusive", "count", "binding"])
def test_reject_invalid_evidence(tmp_path, change):
    p, data = inputs(tmp_path)
    if change.endswith("overlap"):
        key = change.split("_")[0]
        data["samples"][1][key] = data["samples"][0][key]
        p.write_text(json.dumps(data))
    else:
        path = tmp_path / "1-c1"
        row = json.loads(path.read_text())
        if change == "elf_identity": row["elf_sha256"] = "a"*64
        if change == "config_identity": row["config"] = "other"
        if change == "inconclusive": row["inconclusive"] = True
        if change == "count": row["instret"] = 5
        path.write_text(json.dumps(row))
        if change == "binding":
            ev = tmp_path / "1-events"
            row = json.loads(ev.read_text())
            row["trace_sha256"] = "b"*64
            ev.write_text(json.dumps(row))
    with pytest.raises(ValueError):
        calibrate(p, tmp_path / "out")


@pytest.mark.parametrize("count,status", [(None, "missing"), (0, "zero_denominator")])
def test_missing_and_zero_are_explicit(tmp_path, count, status):
    p, _ = inputs(tmp_path)
    ev = tmp_path / "1-events"
    row = json.loads(ev.read_text())
    row["counts"]["issued"] = count
    ev.write_text(json.dumps(row))
    r = calibrate(p, tmp_path / "out")
    e = r["samples"]["heldout"][0]["events"]["issue"]
    assert e["status"] == status
    assert e["error_percent"] is None
    assert not r["budgets"]["observed_events_within_budget"]


def test_later_score_and_changed_prediction_inputs(tmp_path):
    import os
    from datetime import datetime
    from rvw.ooo.evidence import score_prediction
    p, _ = inputs(tmp_path)
    cal, pred, score = [tmp_path / n for n in ("cal", "pred", "score")]
    calibrate(p, cal)
    record = predict(cal, tmp_path / "config", tmp_path / "1-trace", pred)
    later = tmp_path / "later"
    later.write_bytes((tmp_path / "1-c1").read_bytes())
    created = datetime.fromisoformat(record["created_at"]).timestamp()
    os.utime(later, (created+1, created+1))
    result = score_prediction(pred, later, score)
    assert result["prediction_sha256"] == digest(pred)
    assert result["accuracy_status"] == "inconclusive"
    with pytest.raises(FileExistsError):
        score_prediction(pred, later, score)
    os.utime(later, (created-1, created-1))
    with pytest.raises(ValueError, match="after"):
        score_prediction(pred, later, tmp_path / "other")
    with pytest.raises(ValueError, match="heldout"):
        predict(cal, tmp_path / "config", tmp_path / "0-trace", tmp_path / "training-pred")
