from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import run as simulate
from rvw.formal.liveness import run as live
from rvw.results import load_run


@pytest.mark.parametrize('mutant',[False,True])
def test_named_unbounded_engine(tmp_path,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,reset, output ack); reg [1:0] n=0; '
                      'always @(posedge clk) if(reset)n<=0; else n<=n+1; '
                      'assign ack='+('0' if mutant else 'n==2')+'; '
                      'property progress; @(posedge clk) 1 |-> strong(ack[->2]); endproperty '
                      'property alias; progress; endproperty p: assert property(alias); endmodule')
    out=tmp_path/'proof'
    live(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                   backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12))
    result=json.loads((out/'result.json').read_text())
    assert result['observation']==('FAIL' if mutant else 'PASS'),result
    assert result['status']==('fail' if mutant else 'unknown')


@pytest.mark.parametrize('mutant',[False,True])
def test_named_cross_clock_native(tmp_path,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    source.write_text('''module m(input a,b,req,ack,output q); assign q=ack;
property transfer; @(posedge a) req |=> @(posedge b) ack; endproperty
property alias; transfer; endproperty
p: assert property(alias);
property held; logic saved; @(posedge a) (req,saved=ack) |=> ack==saved; endproperty
f: assert property(held);
endmodule''')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(a='0',b='0',req='1',ack='1')),
        dict(time=1,inputs=dict(a='1')),dict(time=2,inputs=dict(a='0')),
        dict(time=3,inputs=dict(req='0',ack='0' if mutant else '1')),
        dict(time=4,inputs=dict(b='1')),dict(time=5,inputs=dict(a='1')),
    ])))
    out=tmp_path/'out'
    simulate(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                       backend='icarus',observe=None,check_x=False,timeout=30))
    result=load_run(out)
    assert result.status==('assert' if mutant else 'pass'),result.to_dict()
    assert result.extra['cross_clock_properties'][0]['id']=='p'
    checks={p['id']:p for p in result.extra['assertions']}
    assert checks['p']['failed']==int(mutant)
    assert checks['f']['failed']==int(mutant)
