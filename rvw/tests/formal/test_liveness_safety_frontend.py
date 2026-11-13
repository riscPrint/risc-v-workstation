from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.liveness import run


@pytest.mark.parametrize('mutant', [False,True])
def test_native_l2s(tmp_path, mutant):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    source = tmp_path/'dut.sv'
    source.write_text('''module m(input clk, reset, req, output ack);
reg [1:0] n=0; always @(posedge clk) if(reset)n<=0; else n<=n+1;
assign ack=''' + ('0;' if mutant else 'n==3;') + '''
p: assert property (@(posedge clk) req |-> s_eventually ack);
endmodule''')
    out = tmp_path/'proof'
    assert run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                         backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12)) == 1
    data = json.loads((out/'result.json').read_text())
    assert data['observation'] == ('FAIL' if mutant else 'PASS'), data
    assert data['status'] == ('fail' if mutant else 'unknown')
    assert data['jobs'][0]['proof_kind'] == ('lasso_counterexample' if mutant else 'liveness_to_safety')
    assert data['jobs'][0]['state_bits'] >= 1


def test_native_justice_binding(tmp_path):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    source = tmp_path/'dut.sv'
    source.write_text('''module m(input clk, reset, req, ack);
f: assume property (@(posedge clk) 1 |-> s_eventually ack);
p: assert property (@(posedge clk) req |-> s_eventually ack);
endmodule''')
    out=tmp_path/'proof'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                  backend='l2s',reset='reset',engine=None,mode='prove',depth=12))
    data=json.loads((out/'result.json').read_text())
    assert data['observation']=='PASS' and data['status']=='unknown', data
    assert data['jobs'][0]['fairness']==['rvw_live_0']


def test_native_range_refusal(tmp_path):
    if not all(shutil.which(tool) for tool in ('yosys','sby')):
        pytest.skip('Yosys and SBY required')
    source=tmp_path/'dut.sv'
    source.write_text('''module m(input clk, reset, req, ack, output [5:2] payload);
assign payload=0;
p: assert property (@(posedge clk) req |-> s_eventually ack);
endmodule''')
    with pytest.raises(ValueError,match='zero-based descending'):
        run(Namespace(source=str(source),top='m',out=str(tmp_path/'proof'),run=True,timeout=30,
                      backend='l2s',reset='reset',engine=None,mode='prove',depth=12))


def test_native_bounded_search_is_not_liveness_proof(tmp_path):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yices-smt2')):
        pytest.skip('Yosys, SBY and Yices required')
    source=tmp_path/'dut.sv'
    source.write_text('''module m(input clk, reset, req, output ack);
reg [1:0] n=0; always @(posedge clk) if(reset)n<=0; else n<=n+1;
assign ack=n==3;
p: assert property (@(posedge clk) req |-> s_eventually ack);
endmodule''')
    out=tmp_path/'proof'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                  backend='l2s',reset='reset',engine=None,mode='bmc',depth=12))
    data=json.loads((out/'result.json').read_text())
    assert data['observation']=='PASS' and data['status']=='unknown',data
    assert data['jobs'][0]['proof_kind']=='bounded_lasso_search'


def test_native_cli_json(tmp_path):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    import subprocess
    import sys
    source=tmp_path/'dut.sv'
    source.write_text('''module m(input clk, reset, req, output ack);
reg [1:0] n=0; always @(posedge clk) if(reset)n<=0; else n<=n+1;
assign ack=n==3;
p: assert property (@(posedge clk) req |-> s_eventually ack);
endmodule''')
    result=subprocess.run(['nice','-n','10',sys.executable,'-m','rvw','formal','liveness',str(source),
                           '--top','m','--out',str(tmp_path/'proof'),'--run','--backend','l2s',
                           '--reset','reset','--timeout','30'],capture_output=True,text=True,timeout=45)
    assert result.returncode==1, result.stderr
    data=json.loads(result.stdout)
    assert data['observation']=='PASS' and data['status']=='unknown'
