"""Opt-in native qualification. Never infer support from a skipped test."""
import os
import json
from pathlib import Path

import pytest

from rvw.results import load_results
from rvw.cli import main

pytestmark = pytest.mark.skipif(not os.environ.get("RVW_UVM_ARCHIVE"),
                                reason="set RVW_UVM_ARCHIVE to the pinned source archive")


def test_accellera_subset_and_rvfi_fault(tmp_path):
    out = tmp_path / "uvm"
    code = main(["regress", "uvm", "--out", str(out),
                 "--archive", os.environ["RVW_UVM_ARCHIVE"],
                 "--verilator", os.environ.get("RVW_UVM_VERILATOR", "verilator"),
                 "--seeds", "3", "--timeout", "600", "--json"])
    report = json.loads((out / "results.json").read_text())
    assert code == 0, report
    assert len(report["tests"]) == 18
    assert all(row["status"] == "pass" for row in report["tests"]), report
    for row in report["tests"]:
        assert not row["wall_clock_timeout"]
        assert (row["simulator_exit"] != 0) == (row["id"] == "rvfi_fault_detection")
    loaded = load_results(out)
    assert len(loaded.tests) == 18
    assert all(row.conclusive for row in loaded.tests)
