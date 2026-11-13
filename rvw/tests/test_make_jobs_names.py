"""RiscvSim's make wrapper maps raw public-signal names to Verilator 5's encoded member names."""
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.fast

SCRIPT = Path(__file__).resolve().parents[2] / "RiscvSim/scripts/make-jobs.sh"


def run(tmp_path, header: str, access: str) -> str:
    build = tmp_path / "verilator"
    build.mkdir(exist_ok=True)
    (build / "VTop_Top.h").write_text(header)
    wrapper = build / "VTop__spinalWrapper.cpp"
    wrapper.write_text(f"signalAccess[0] = new CDataSignalAccess( {access} );\n")
    env = dict(os.environ, RISCVSIM_MAKE="true")
    env.pop("RISCVSIM_PINNED_BIN", None)
    subprocess.run(["bash", str(SCRIPT), "-C", str(build), "-f", "VTop.mk"], check=True, env=env)
    return wrapper.read_text()


def test_raw_names_missing_from_the_headers_take_the_encoded_form(tmp_path):
    header = "CData/*0:0*/ rvwprobe___05Fcounter___05Fa___05Finc;\nCData rvw_plain;\n"
    out = run(tmp_path, header, "top->Top->rvwprobe__counter__a__inc")
    assert "top->Top->rvwprobe___05Fcounter___05Fa___05Finc" in out
    assert run(tmp_path, header, "top->Top->rvw_plain").count("top->Top->rvw_plain") == 1


def test_names_that_the_headers_declare_stay_unchanged(tmp_path):
    raw = "CData rvwprobe__counter__a__inc;\n"
    assert "top->Top->rvwprobe__counter__a__inc" in run(tmp_path, raw, "top->Top->rvwprobe__counter__a__inc")
    encoded = "CData rvwprobe___05Fcounter___05Fa___05Finc;\n"
    out = run(tmp_path, encoded, "top->Top->rvwprobe___05Fcounter___05Fa___05Finc")
    assert "___05F___05F" not in out and "rvwprobe___05Fcounter___05Fa___05Finc" in out
