"""`rvw perf topdown`: commit-slot partition from counter probes, checked against C2 and C1."""
import json
from pathlib import Path

import pytest

from rvw.perf import topdown
from rvw.perf.cli import execute_json

pytestmark = pytest.mark.fast

NAMES = ["topdown_slots", "topdown_retiring", "topdown_bad_speculation", "topdown_backend_bound",
         "topdown_frontend_bound"]


def stream(tmp_path: Path, counters: dict, end=True) -> Path:
    path = tmp_path / "probe-events.jsonl"
    probes = [{"id": i, "kind": "counter", "name": n, "fields": [["inc", 2]], "meta": {}}
              for i, n in enumerate(counters)]
    lines = [json.dumps({"schema": "rvw.probe-events/1", "identity": {"core": "t"}, "probes": probes})]
    if end:
        lines.append(json.dumps({"end": True, "cycles": 10, "counters": counters}))
    path.write_text("\n".join(lines) + "\n")
    return path


def c2(tmp_path: Path, retired: int) -> Path:
    path = tmp_path / "rvfi.jsonl"
    rows = [{"schema": "rvw.rvfi/1", "xlen": 32}]
    rows += [{"order": i, "pc": "0x0", "insn": "0x13", "trap": False} for i in range(retired)]
    rows += [{"event": "trap", "cycle": 3, "cause": "0x2"}, {"event": "end", "status": "pass"}]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def good():
    return dict(zip(NAMES, [20, 6, 4, 8, 2]))


def test_partition_is_reported_and_checked_against_c2_and_c1(tmp_path):
    result = tmp_path / "result.json"
    result.write_text(json.dumps({"instret": 6}))
    r = topdown.report(stream(tmp_path, good()), c2=c2(tmp_path, 6), c1=result)
    assert r["status"] == "checked" and r["width"] == 2
    assert r["fractions"] == {"retiring": .3, "bad_speculation": .2, "backend_bound": .4, "frontend_bound": .1}
    assert "retiring" in topdown.render(r)
    via_cli = execute_json(["topdown", str(tmp_path / "probe-events.jsonl")], c2=str(tmp_path / "rvfi.jsonl"))
    assert via_cli["slots"] == r["slots"]


def test_without_c2_the_report_is_unchecked(tmp_path):
    assert topdown.report(stream(tmp_path, good()))["status"] == "unchecked"


@pytest.mark.parametrize("change, message", [
    (dict(topdown_frontend_bound=3), "sum to"),
    (dict(topdown_slots=0), "sum to"),
])
def test_a_partition_that_does_not_cover_the_slots_is_refused(tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        topdown.report(stream(tmp_path, {**good(), **change}))


def test_retiring_must_equal_the_c2_retirements(tmp_path):
    with pytest.raises(ValueError, match="C2 retirements"):
        topdown.report(stream(tmp_path, good()), c2=c2(tmp_path, 5))


def test_missing_counters_and_incomplete_runs_are_refused(tmp_path):
    counters = good()
    del counters["topdown_backend_bound"]
    with pytest.raises(ValueError, match="lacks top-down counters"):
        topdown.report(stream(tmp_path, counters))
    with pytest.raises(ValueError, match="no end record"):
        topdown.report(stream(tmp_path, good(), end=False))
