"""Opt-in native qualification. Never infer support from a skipped test."""
import os
import json
from pathlib import Path

import pytest

from rvw.results import load_results
from rvw.common.proc import run_group
from rvw.cli import main
from rvw.sim.uvm import FEATURES

pytestmark = [
    pytest.mark.slow(reason="compile pinned Accellera UVM on Verilator and run three seeds"),
    pytest.mark.skipif(not os.environ.get("RVW_UVM_ARCHIVE"),
                       reason="set RVW_UVM_ARCHIVE to the pinned source archive"),
]


def test_accellera_subset_and_rvfi_fault(tmp_path):
    out = tmp_path / "uvm"
    code = main(["regress", "uvm", "--out", str(out),
                 "--archive", os.environ["RVW_UVM_ARCHIVE"],
                 "--verilator", os.environ.get("RVW_UVM_VERILATOR", "verilator"),
                 "--seeds", "3", "--timeout", "600", "--json"])
    report = json.loads((out / "results.json").read_text())
    # A constant random stream must still fail the observed-data check.
    control = run_group([str(out / "build/Vtop"), "+verilator+seed+1",
                         "+constant_data"], capture=True, timeout=20)
    assert control.returncode != 0
    assert "random data did not change" in control.stdout + control.stderr

    assert code == 0, report
    assert len(report["tests"]) == 3 * (len(FEATURES) + 3)
    assert all(row["status"] == "pass" for row in report["tests"]), report
    for row in report["tests"]:
        assert not row["wall_clock_timeout"]
        assert (row["simulator_exit"] != 0) == row["id"].endswith("fault_detection")
    loaded = load_results(out)
    assert len(loaded.tests) == 3 * (len(FEATURES) + 3)
    assert all(row.conclusive for row in loaded.tests)

