"""Optional short native pyuvm fixture. Run under nice -n 10."""
import importlib.util
from pathlib import Path
import shutil
import pytest
from rvw.sim.cocotb import run
from rvw.results import load_results


def test_pyuvm_base_native(tmp_path):
    if not shutil.which('verilator') or not importlib.util.find_spec('pyuvm') or not importlib.util.find_spec('cocotb_tools'):
        pytest.skip('Verilator, pyuvm 4 and cocotb 2 are required')
    root=Path(__file__).resolve().parents[2]
    report=run(root/'Uvm/pyuvm/bench.json',tmp_path/'native',timeout=110)
    assert len(report['tests'])==1
    assert report['tests'][0]['status']=='pass'
    assert len(load_results(tmp_path/'native').tests)==1
