import json
import shutil
from pathlib import Path
import pytest
from rvw.common.proc import run_group
from rvw.formal.csr_bank import load,monitor

pytestmark=pytest.mark.slow


@pytest.mark.parametrize('fault',['none','state','read','privilege_good','privilege_bad'])
def test_shared_alias_proof(tmp_path,fault):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    root=Path(__file__).resolve().parents[3]
    obj=load(root/'SpinalChecks/csr/bank-example.json')
    low_priv=fault.startswith('privilege')
    source=monitor(obj)+f'''module fixture(input clk);
reg [3:0] phase=0; always @(posedge clk) if(phase<7) phase<=phase+1;
wire reset=phase==0, valid=phase>=1 && phase<=3, wr=phase==1 || phase==2, rd=phase==3;
wire [1:0] privilege={0 if low_priv else 3};
wire [11:0] address=phase==1 ? 1 : phase==2 ? 2 : {832 if low_priv else 3};
wire [31:0] data=phase==1 ? 1 : 2, rdata={64 if fault=='read' else 65};
wire trap=phase==3 && {1 if fault=='privilege_good' else 0};
wire [7:0] state_fp=phase<2 ? 0 : phase<3 ? 1 : phase<5 ? {64 if fault=='state' else 65} : {80 if fault=='state' else 81};
wire [7:0] hw_set_fp=phase==4 ? 16 : 0, hw_clear_fp=0;
wire [31:0] state_machine=0,state_supervisor=0,hw_set_machine=0,hw_clear_machine=0,hw_set_supervisor=0,hw_clear_supervisor=0;
rvw_csr_bank dut(.*); endmodule
'''
    (tmp_path/'design.sv').write_text(source)
    (tmp_path/'proof.sby').write_text('''[options]
mode prove
depth 12
[engines]
smtbmc yices
[script]
read -formal design.sv
prep -top fixture
[files]
design.sv
''')
    r=run_group(['nice','-n','10','sby','-f','proof.sby'],cwd=tmp_path,capture=True,timeout=45)
    status=tmp_path/'proof/status'
    assert status.exists(),r.stdout+r.stderr
    assert status.read_text().split()[0]==('PASS' if fault in ('none','privilege_good') else 'FAIL'),r.stdout+r.stderr
