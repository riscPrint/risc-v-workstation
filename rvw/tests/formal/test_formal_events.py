"""Independent expected results for event clocks and asynchronous reset pulses."""
import json
import shutil
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.formal import common

pytestmark = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("yosys", "sby", "yices-smt2")), reason="needs formal tools")
REFERENCES = Path(__file__).resolve().parents[3] / "SpinalChecks" / "examples" / "events"


def run(tmp_path, design, *options):
    out = tmp_path / "out"
    try:
        rc = main(["formal", "bmc", "--verilog", str(REFERENCES / (design + ".sv")),
                   "--top", "top", "--depth", "14", "--timeout", "30", "--out", str(out),
                   "--json", *options])
    except SystemExit as e:
        rc = e.code
    result = json.loads((out / "result.json").read_text()) if (out / "result.json").exists() else None
    return rc, result, out


@pytest.mark.parametrize("design,status", [("clocks_pass", "pass"), ("clocks_fail", "fail")])
def test_unrelated_clocks(tmp_path, design, status):
    rc, result, out = run(tmp_path, design, "--event-clock", "other_clk")
    assert result["status"] == status
    assert rc == (0 if status == "pass" else 1)
    assert result["event_model"]["clocks"] == ["clk", "other_clk"]
    assert "multiclock on" in (out / "bmc.sby").read_text()


@pytest.mark.parametrize("design,status", [("async_pass", "pass"), ("async_fail", "fail"),
                                         ("async_low_pass", "pass"), ("async_low_fail", "fail")])
def test_inter_edge_reset_pulse(tmp_path, design, status):
    rc, result, _ = run(tmp_path, design, "--event-model", "--async-reset")
    assert result["status"] == status
    assert rc == (0 if status == "pass" else 1)
    assert result["event_model"]["async_reset"]
    if status == "fail":
        assert all(f["cycle"] is None for f in result["failures"])


@pytest.mark.parametrize("design,options", [
    ("clocks_fail", ["--event-model"]),  # undeclared other clock
    ("async_fail", ["--event-model"]),  # async reset is independent opt-in
    ("async_fail", ["--async-reset"]),  # sync backend must never accept it
    ("gated", ["--event-model"]),
    ("latch", ["--event-model", "--async-reset"]),
    ("async_load", ["--event-model", "--async-reset"]),
    ("raw_async_assert", ["--event-model", "--async-reset"]),
    ("falling", ["--event-model"]),
    ("clocks_pass", ["--event-clock", "missing"]),
])
def test_unsupported_cases_stay_refused(tmp_path, design, options):
    rc, result, _ = run(tmp_path, design, *options)
    assert rc == 2 and result is None


def test_async_enable_does_not_allow_other_state():
    for kind in ("$aldff", "$dffsr", "$dlatch", "$future_ff"):
        assert common.async_state_problems({"top": {"cells": {"q": {
            "type": kind, "connections": {}}}}}, allow_async_reset=True)


def test_mcp_forwards_separate_event_options():
    from rvw.formal.mcp_tools import _argv
    argv = _argv("bmc", {"event_model": True, "async_reset": True, "event_clock": ["c2", "c3"]})
    assert argv[-6:] == ["--event-model", "--async-reset", "--event-clock", "c2", "--event-clock", "c3"]


@pytest.mark.parametrize("options", [
    ["--event-clock", "clk"],
    ["--event-clock", "other_clk", "--event-clock", "other_clk"],
    ["--event-clock", "other_clk", "--tie", "other_clk=0"],
    ["--event-clock", "other_clk", "--reset", "other_clk"],
])
def test_invalid_clock_declarations(tmp_path, options):
    rc, result, _ = run(tmp_path, "clocks_pass", *options)
    assert rc == 2 and result is None
