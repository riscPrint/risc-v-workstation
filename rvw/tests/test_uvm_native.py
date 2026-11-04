"""Opt-in native qualification. Never infer support from a skipped test."""
import os
from pathlib import Path

import pytest

from rvw.results import load_results
from rvw.sim.uvm import run

pytestmark = pytest.mark.skipif(not os.environ.get("RVW_UVM_ARCHIVE"),
                                reason="set RVW_UVM_ARCHIVE to the pinned source archive")


def test_accellera_subset_and_rvfi_fault(tmp_path):
    out = tmp_path / "uvm"
    report = run(out, archive=Path(os.environ["RVW_UVM_ARCHIVE"]),
                 verilator=os.environ.get("RVW_UVM_VERILATOR", "verilator"),
                 seeds=3, timeout=600)
    assert len(report["tests"]) == 18
    assert all(row["status"] == "pass" for row in report["tests"]), report
    loaded = load_results(out)
    assert len(loaded.tests) == 18
    assert all(row.conclusive for row in loaded.tests)
