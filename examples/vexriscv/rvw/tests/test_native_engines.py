"""Explicit captured-RTL engine qualification. No core source build in this test."""
import json
import os
from pathlib import Path
import pytest
from rvw.common.proc import run_group
from rvw.results import load_run


def test_real_core_c1_and_bit_identical_c2(tmp_path):
    rtl=os.environ.get('RVW_VEX_ENGINE_RTL');elf=os.environ.get('RVW_VEX_ENGINE_ELF')
    if not rtl or not elf:pytest.skip('captured RTL and smoke ELF must be selected explicitly')
    import sys
    launcher=Path(__file__).resolve().parents[1]/'engine-probe.py'
    for backend in ('arcilator','verilator'):
        out=tmp_path/backend
        result=run_group(['nice','-n','10',sys.executable,str(launcher),'--backend',backend,
            '--rtl',rtl,'--elf',elf,'--seed','7','--out',str(out)],timeout=120,capture=True)
        assert result.returncode==0,result.stdout+result.stderr
        run=load_run(out)
        assert run.status=='pass' and run.instret==17 and run.cycles==81
    assert (tmp_path/'arcilator/rvfi.jsonl').read_bytes()==(tmp_path/'verilator/rvfi.jsonl').read_bytes()
