"""Project binding consistency and opt-in live VexRiscv scoreboard test."""
import json
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'Uvm/examples/vexriscv'


def test_binding_covers_strict_cpu_fields():
    from rvw.sim.cpu_env import CpuScoreboard
    binding = json.loads((HERE/'bindings.json').read_text())
    assert set(binding['fields']) == set(CpuScoreboard.fields +
        'order rs1 rs1_rdata rs2 rs2_rdata intr halt'.split()) - {'mem_fault'}
    assert len(set(binding['fields'].values())) == len(binding['fields'])
    assert all(pin.startswith('rvfi_') for pin in binding['fields'].values())
    assert 'timerInterrupt' in binding['zero_inputs']
    assert 'externalInterrupt' in binding['zero_inputs']


@pytest.mark.skipif(not os.environ.get('RVW_VEX_LIVE_ELF'),
                    reason='set RVW_VEX_LIVE_ELF and RVW_CPU_SHIM; generate VexTop.v first')
def test_live_vex_spike_and_corruption(tmp_path, monkeypatch):
    from rvw.sim.cocotb import run
    monkeypatch.setenv('RVW_CPU_ELF', os.environ['RVW_VEX_LIVE_ELF'])
    monkeypatch.delenv('RVW_VEX_CORRUPT', raising=False)
    report = run(HERE/'bench.json', tmp_path/'good', timeout=120)
    assert len(report['tests']) == 6
    assert all(t['status'] == 'pass' for t in report['tests'])
    for program in ('add', 'beq', 'lw', 'sw', 'jal', 'xor'):
        name = 'rv32ui-p-'+program
        evidence = json.loads((tmp_path/'good'/('cpu-checks-'+name+'.json')).read_text())
        assert evidence['checks'] > 5 and evidence['traps'] > 0
        assert (tmp_path/'good'/('spike-capture-'+name)).is_dir()
    checks = json.loads((tmp_path/'good/cpu-checks.json').read_text())
    assert checks['checks'] > 5
    assert checks['coverage']['samples'] == checks['checks']
    monkeypatch.setenv('RVW_VEX_CORRUPT', '1')
    report = run(HERE/'bench.json', tmp_path/'bad', timeout=120)
    assert all(t['status'] == 'fail' for t in report['tests'])
    assert 'SPIKE_MISMATCH:pc_next' in (tmp_path/'bad/run.log').read_text()
    assert not (tmp_path/'bad/cpu-checks.json').exists()
