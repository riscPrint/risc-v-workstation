"""Opt-in native VexRiscv IRQ and catalog CSR qualification."""
import json
import os
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'Uvm/examples/vexriscv'

@pytest.mark.skipif(not os.environ.get('RVW_VEX_EVENTS_DIR'),reason='build IRQ and CSR ELFs and set RVW_VEX_EVENTS_DIR')
@pytest.mark.parametrize('program,seed',[('irq',1),('irq',3),('csr',1)])
def test_native_events(tmp_path,monkeypatch,program,seed):
    from rvw.sim.cocotb import run
    monkeypatch.setenv('RVW_CPU_ELF',str(Path(os.environ['RVW_VEX_EVENTS_DIR'])/(program+'.elf')))
    monkeypatch.setenv('RVW_VEX_SEED',str(seed))
    monkeypatch.delenv('RVW_VEX_CORRUPT',raising=False)
    monkeypatch.delenv('RVW_VEX_IRQ',raising=False)
    monkeypatch.delenv('RVW_VEX_CSR_SELECTION',raising=False)
    if program=='irq': monkeypatch.setenv('RVW_VEX_IRQ','1')
    else: monkeypatch.setenv('RVW_VEX_CSR_SELECTION',str(HERE/'csr.json'))
    report=run(HERE/'bench.json',tmp_path/'run',seed=seed,timeout=120)
    assert len(report['tests'])==1 and report['tests'][0]['status']=='pass'
    counts=json.loads((tmp_path/'run/cpu-checks.json').read_text())
    assert counts['checks']>0
    if program=='irq': assert counts['interrupts']==8
    else: assert counts['csr_qualification']['checks']==88
