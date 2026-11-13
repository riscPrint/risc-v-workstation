"""Opt-in connected Spinal APB/AXI-Lite/UART test."""
import json
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.skipif(not os.environ.get('RVW_UVM_SOC_NATIVE'), reason='generate SeededSoc RTL and set RVW_UVM_SOC_NATIVE=1')
@pytest.mark.parametrize('seed', [1, 7])
def test_connected_soc(tmp_path, monkeypatch, seed):
    from rvw.sim.cocotb import run
    monkeypatch.setenv('RVW_SOC_SEED', str(seed))
    report = run(ROOT/'Uvm/examples/soc/bench.json', tmp_path/'run', seed=seed, timeout=120)
    assert len(report['tests']) == 1 and report['tests'][0]['status'] == 'pass'
    checks = json.loads((tmp_path/'run/soc-checks.json').read_text())
    assert checks['cpu_checks'] == 0
    assert checks['bus_checks'] == {'control':9, 'serial':9}
    assert checks['uart_frames'] == 4
