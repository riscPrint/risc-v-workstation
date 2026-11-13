from argparse import Namespace
import json
import shutil
import subprocess

import pytest

from rvw.formal.liveness import lower_live,run


FUNCTIONS = ['past','rose','fell','stable','changed']


@pytest.mark.parametrize('function',FUNCTIONS)
@pytest.mark.parametrize('mutant',[False,True])
def test_sampled_liveness_engine(tmp_path,function,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    good='n[1]'
    bad='n[0]' if function=='stable' else '0'
    sampled='$past(ack,2)' if function=='past' else '$'+function+'(ack)'
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,reset,output ack); reg [1:0] n=0; '
                      'always @(posedge clk) if(reset)n<=0; else n<=n+1; '
                      'assign ack='+ (bad if mutant else good)+'; '
                      'p: assert property (@(posedge clk) 1 |-> s_eventually '+sampled+'); endmodule')
    out=tmp_path/'proof'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                  backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12))
    result=json.loads((out/'result.json').read_text())
    assert result['observation']==('FAIL' if mutant else 'PASS'),result
    assert result['status']==('fail' if mutant else 'unknown')


def test_nested_history_and_signed_width_native(tmp_path):
    if not all(shutil.which(tool) for tool in ('iverilog','vvp')):
        pytest.skip('Icarus required')
    source='''module m(input clk,input signed [7:0] data);
assert property (@(posedge clk) 1 |-> s_eventually ($past($past(data))<0)); endmodule'''
    rtl,_,_=lower_live(source,'m')
    (tmp_path/'m.sv').write_text(rtl+'''
module tb; reg clk=0; reg signed [7:0] data=-1; m dut(clk,data);
initial begin repeat(8) begin #1; clk=1; #1; $display("%b",dut.rvw_live_0); clk=0; end $finish; end endmodule
''')
    compiled=subprocess.run(['nice','-n','10','iverilog','-g2012','-s','tb','-o','sim','m.sv'],cwd=tmp_path,
                            capture_output=True,text=True,timeout=30)
    assert compiled.returncode==0,compiled.stderr
    result=subprocess.run(['nice','-n','10','vvp','sim'],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    values=[line for line in result.stdout.splitlines() if line in ('0','1','x','z')]
    assert values[-3:]==['1']*3,result.stdout
