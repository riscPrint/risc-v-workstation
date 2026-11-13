import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.micro_checks import NAMES, render

pytestmark=pytest.mark.slow


@pytest.mark.parametrize('kind',NAMES)
@pytest.mark.parametrize('bad',[False,True])
def test_micro_proofs(tmp_path,kind,bad):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    ports={
      'fifo_order':f'wire push=phase==1, pop=phase==2; wire [7:0] push_data=42, pop_data={41 if bad else 42};',
      'pipeline':f'wire valid=1, ready=0; wire [7:0] payload={"phase" if bad else "42"};',
      'mutex':f'wire [2:0] grants={3 if bad else 1};',
      'arbiter':f'wire enabled=1; wire [2:0] requests=1, grants={0 if bad else 1};',
      'age_matrix':f'wire [2:0] valid=7; wire [8:0] older={0 if bad else 38};',
      'store_forward':f'wire load_fire=1, forwarded=1; wire [2:0] valid=7, older=7, address_match=7, selected={1 if bad else 4}; wire [7:0] load_data=3; wire [23:0] store_data=24\'h030201;'
    }[kind]
    source=render(kind,8,3)+f'''module fixture(input clk);
reg [3:0] phase=0; always @(posedge clk) if(phase<12) phase<=phase+1;
wire reset=phase==0; {ports}
rvw_{kind} dut(.*); endmodule
'''
    (tmp_path/'design.sv').write_text(source)
    (tmp_path/'proof.sby').write_text('''[options]
mode prove
depth 16
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
    assert status.read_text().split()[0] == ('FAIL' if bad else 'PASS'),r.stdout+r.stderr


def test_project_signals_and_missing_bindings(tmp_path):
    from rvw.formal.micro_checks import generate
    result=generate(dict(schema='rvw.micro-checks/1',top='Top',rules=[
        dict(id='grants',kind='mutex',entries=4,ports=dict(clk='clk',reset='reset',grants='io_grants')),
        dict(id='missing',kind='fifo_order',ports={})]),tmp_path/'out')
    assert result['status']=='generated'
    assert not result['complete']
    assert result['rules'][1]['status']=='unsupported'
    assert 'push_data' in result['rules'][1]['reason']
    assert '.grants(io_grants)' in (tmp_path/'out/binds.sv').read_text()
