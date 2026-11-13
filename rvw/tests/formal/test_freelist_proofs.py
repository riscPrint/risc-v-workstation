import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.resource_checks import render

pytestmark=pytest.mark.slow


@pytest.mark.parametrize('case',['good','nonempty_reset','missing_free','duplicate_free','lost_live','reserved_tag'])
def test_freelist_partition_and_ownership(tmp_path,case):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):pytest.skip('SBY and Yices required')
    initial=1 if case=='nonempty_reset' else 0
    tag=3 if case=='reserved_tag' else 1
    live=f'(phase==2 || phase==3) ? {initial|(1<<tag)} : {initial}'
    if case=='lost_live':live='0'
    free='(~live & 7)'
    if case=='missing_free':free='(~live & 6)'
    if case=='duplicate_free':free='7'
    source=render('freelist_conservation',3,4)+f'''module fixture(input clk);
reg [3:0] phase=0;always @(posedge clk)if(phase<8)phase<=phase+1;wire reset=phase==0;
wire [3:0] live={live},free_bits={free};
wire alloc0_valid=phase==1,alloc1_valid=0,free0_valid=phase==3,free1_valid=0;
wire [2:0] alloc0={tag},alloc1=0,free0={tag},free1=0;
rvw_freelist_conservation #(.INITIAL_LIVE(4'd{initial}),.USABLE(4'd7)) dut(.*);endmodule
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
    r=run_group(['nice','-n','10','sby','-f','proof.sby'],cwd=tmp_path,capture=True,timeout=30)
    status=tmp_path/'proof/status'
    assert status.exists(),r.stdout+r.stderr
    assert status.read_text().split()[0]==('PASS' if case in ('good','nonempty_reset') else 'FAIL'),r.stdout+r.stderr
