from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.liveness import run


@pytest.mark.parametrize('sequence',[
    '1 ##[1:$] c', 'b[*1:$] ##1 c', 'b[->1] ##1 c', 'b[=1] ##1 c',
    'b[->1:2] ##1 c', 'b[=1:2] ##1 c',
])
@pytest.mark.parametrize('mutant',[False,True])
def test_native_throughout_completion(tmp_path,sequence,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    # g is false in an idle phase even in the legal design. The last completion
    # sample still needs g. Fault g is false while an attempt is active.
    g='n!=1' if mutant else 'n<3'
    b='n<2' if ':2]' in sequence or '[*' in sequence else 'n==1'
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,reset); reg [1:0] n=0; '
                      'always @(posedge clk) if(reset)n<=0; else n<=n+1; '
                      'wire req=!reset && n==0; wire b='+b+'; wire c=n==2; wire g='+g+'; '
                      'assert property (@(posedge clk) req |-> strong(g throughout ('+sequence+'))); endmodule')
    out=tmp_path/'proof'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                  backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12))
    result=json.loads((out/'result.json').read_text())
    assert result['observation']==('FAIL' if mutant else 'PASS'),(sequence,result)


@pytest.mark.parametrize('mutant',[False,True])
def test_native_weak_waiting_guard(tmp_path,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,reset); reg [1:0] n=0; '
                      'always @(posedge clk) if(reset)n<=0; else n<=n+1; '
                      'wire g='+('n!=1' if mutant else '1')+'; '
                      'assert property (@(posedge clk) !reset |-> (g throughout (1 ##[0:$] 0))); endmodule')
    out=tmp_path/'proof'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                  backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12))
    result=json.loads((out/'result.json').read_text())
    assert result['observation']==('FAIL' if mutant else 'PASS'),result
