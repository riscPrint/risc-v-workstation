"""Optional native checks of generated RAL and standard UVM sequences."""
import os
from pathlib import Path
import shutil
import pytest
from rvw.sim import uvm, ral
from rvw.common.proc import run_group


def test_generated_ral_builtin_sequences(tmp_path):
    archive = os.environ.get('RVW_UVM_ARCHIVE')
    if not archive or not shutil.which('verilator'):
        pytest.skip('set RVW_UVM_ARCHIVE and install Verilator for native RAL')
    root = Path(__file__).resolve().parents[2]
    library = uvm.unpack(Path(archive), tmp_path/'library')
    (tmp_path/'ral.sv').write_text(ral.generate(root/'Uvm/tests/registers.json'))
    command = ['nice','-n','10','verilator','--binary','--timing','--assert',
        '-Wno-fatal','-j','2','--top-module','top','+define+UVM_NO_DPI',
        '+incdir+'+str(library/'src'),str(library/'src/uvm_pkg.sv'),
        str(tmp_path/'ral.sv'),str(root/'Uvm/base/rvw_ral_pkg.sv'),
        str(root/'Uvm/examples/ral/top.sv'),'--Mdir',str(tmp_path/'obj'),
        '-MAKEFLAGS','OPT_FAST=-O0 OPT_SLOW=-O0']
    with (tmp_path/'build.log').open('w') as log:
        result = run_group(command, timeout=120, stdout=log, stderr=log)
    assert not result.timed_out and result.returncode == 0
    result = run_group(['nice','-n','10',str(tmp_path/'obj/Vtop')], capture=True, timeout=15)
    assert not result.timed_out and result.returncode == 0
    assert 'RVW_UVM_DONE ral_smoke checks=524' in result.stdout
    for name in ('uvm_reg_hw_reset_seq','uvm_reg_bit_bash_seq','uvm_reg_access_seq'):
        assert name in result.stdout
    assert 'UVM_ERROR :    0' in result.stdout and 'UVM_FATAL :    0' in result.stdout
