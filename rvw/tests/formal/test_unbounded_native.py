"""Small paired native jobs and emitted-monitor trace checks."""
from argparse import Namespace
import json
import shutil
import subprocess

import pytest

from rvw.formal.liveness import lower_live, run


def tools(*names):
    if not all(shutil.which(name) for name in names):
        pytest.skip(', '.join(names)+' required')


CASES = [
    ('s_eventually', 's_eventually b', 'b=phase==2', 'b=0'),
    ('until', 'a until b', 'a=phase<3; b=phase==2', 'a=phase==0; b=phase==2'),
    ('until_with', 'a until_with b', 'a=phase<3; b=phase==2', 'a=phase==0; b=phase==2'),
    ('s_until', 'a s_until b', 'a=phase<3; b=phase==2', 'a=phase==0; b=phase==2'),
    ('s_until_with', 'a s_until_with b', 'a=phase<3; b=phase==2', 'a=phase==0; b=phase==2'),
    ('##[M:$]', 'strong(##[2:$] b)', 'b=phase==2', 'b=0'),
    ('[*M:$]', 'strong(a[*1:$] ##1 b)', 'a=phase<3; b=phase==2', 'a=phase==0; b=phase==2'),
    ('[*]', 'strong(a[*] ##1 b)', 'a=phase<3; b=phase==2', 'a=phase==0; b=phase==2'),
    ('[->N]', 'strong(b[->2])', 'b=phase==2', 'b=0'),
    ('[=N]', 'strong(b[=2])', 'b=phase==2', 'b=0'),
    ('strong / weak', 'strong(b[->2] ##1 a)', 'b=phase==2; a=phase==3', 'b=phase==2; a=0'),
    ('unbounded first_match', 'strong(first_match(b[=2] ##1 a))', 'b=phase==2; a=phase==0', 'b=phase==2; a=0'),
]


@pytest.mark.parametrize('feature,expr,good,bad', CASES)
@pytest.mark.parametrize('mutant',[False,True])
def test_native_paired(tmp_path, feature, expr, good, bad, mutant):
    tools('yosys','sby','yosys-abc')
    assignments='; assign '.join((bad if mutant else good).split('; '))
    if 'a=' not in assignments:
        assignments += '; assign a=1'
    if 'b=' not in assignments:
        assignments += '; assign b=1'
    source=tmp_path/'dut.sv'
    source.write_text('module m(input clk, reset, output a,b); '
                      'reg [1:0] phase=0; always @(posedge clk) if(reset)phase<=0; else phase<=phase+1; '
                      'wire req=phase==0; assign '+assignments+'; '
                      'p: assert property (@(posedge clk) req |-> '+expr+'); endmodule')
    out=tmp_path/'proof'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                  backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12))
    data=json.loads((out/'result.json').read_text())
    assert data['observation']==('FAIL' if mutant else 'PASS'), (feature,data)
    assert data['status']==('fail' if mutant else 'unknown')


@pytest.mark.parametrize('expr,expected',[
    ('1 |-> strong(b[->3])', True),
    ('1 |=> strong(b[->3])', True),
    ('1 |-> strong(b[=3])', True),
    ('1 |-> b[->3]', True),
    ('1 |-> a until b', True),
    ('1 |-> a s_until b', False),
    ('1 |-> weak(b[->3])', True),
    ('1 |-> strong(b[->3])', False),
    ('1 |-> strong(b[->1] ##1 a)', False),
    ('1 |-> strong(b[=1] ##1 a)', True),
    ('1 |-> a until_with b', False),
    ('1 |-> a until b', True),
])
def test_emitted_lasso_trace(tmp_path, expr, expected, request):
    tools('iverilog','vvp')
    index=request.node.callspec.indices['expr']
    # Continuous event/request tests catch obligation overwrites and starvation.
    # The later tests distinguish weak/strong, goto/nonconsecutive and inclusive until.
    trace = ([(True,True)] if index<3 else [(True,False)] if index<8
             else [(False,True),(False,False),(True,False),(False,False)] if index<10
             else [(True,False),(False,True)])
    rtl,_,_=lower_live('module m(input clk,a,b); p: assert property (@(posedge clk) '+expr+'); endmodule','m')
    tb='module tb; reg clk=0,a=0,b=0; m dut(clk,a,b); initial begin\n'
    for i in range(80):
        a,b=trace[i%len(trace)]
        tb += f"a={int(a)}; b={int(b)}; #1; clk=1; #1; $display(\"%b\", dut.rvw_live_0); clk=0; #1;\n"
    tb += '$finish; end endmodule\n'
    (tmp_path/'m.sv').write_text(rtl+'\n'+tb)
    compiled=subprocess.run(['nice','-n','10','iverilog','-g2012','-s','tb','-o','sim','m.sv'],
                            cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert compiled.returncode==0,compiled.stderr
    simulated=subprocess.run(['nice','-n','10','vvp','sim'],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert simulated.returncode==0,simulated.stderr
    assert ('1' in simulated.stdout.splitlines()[-24:]) == expected, (expr,simulated.stdout)
