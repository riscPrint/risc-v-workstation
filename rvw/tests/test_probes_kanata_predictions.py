"""Kanata prediction records from branch probes that carry the instruction ID."""
import json

import pytest

from rvw.perf import kanata as kreader
from rvw.probes import api

pytestmark = pytest.mark.fast


def write(tmp_path, probes, rows, name="probe-events.jsonl"):
    lines = [{"schema": "rvw.probe-events/1", "identity": {}, "probes": probes}, *rows,
             {"end": True, "cycles": 10, "counters": {}, "events": {}}]
    path = tmp_path / name
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def probes(with_id=True):
    branch = ["pc", "taken", "target", "predicted_taken"] + (["id"] if with_id else [])
    return [{"id": 0, "kind": "stage", "name": "W", "fields": [["id", 8], ["pc", 32]], "meta": {"stage": "W", "lane": "0"}},
            {"id": 1, "kind": "branch", "name": "static", "fields": [[f, 32] for f in branch],
             "meta": {"semantics": "final-prediction", "covers": "cond"}},
            {"id": 2, "kind": "retire", "name": "wb", "fields": [["id", 8]], "meta": {}}]


def test_branch_with_id_writes_direction_outcomes_perf_reads(tmp_path):
    rows = [[1, 0, 5, 0x100], [1, 1, 0x100, 1, 0x80, 1, 5], [1, 2, 5],
            [2, 0, 6, 0x104], [2, 1, 0x104, 1, 0x120, 0, 6], [2, 2, 6]]
    out = tmp_path / "k.log"
    rep = api.run_convert(write(tmp_path, probes(), rows), "kanata", out)
    assert rep["predictions"] == 2 and rep["retired"] == 2
    t = kreader.read(out)
    assert [(p["predictor"], p["correct"]) for p in t.predictions] == [("static", True), ("static", False)]


def test_branch_without_id_adds_no_prediction(tmp_path):
    rows = [[1, 0, 5, 0x100], [1, 1, 0x100, 1, 0x80, 1], [1, 2, 5]]
    rep = api.run_convert(write(tmp_path, probes(False), rows), "kanata", tmp_path / "k.log")
    assert rep["predictions"] == 0


def test_branch_id_that_is_not_live_is_refused(tmp_path):
    rows = [[1, 0, 5, 0x100], [1, 2, 5], [2, 1, 0x100, 1, 0x80, 1, 5]]
    with pytest.raises(ValueError, match="not a live instruction"):
        api.run_convert(write(tmp_path, probes(), rows), "kanata", tmp_path / "k.log")
