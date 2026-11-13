from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


@pytest.mark.parametrize('backend',['icarus','verilator'])
@pytest.mark.parametrize('mutant',[False,True])
def test_native_assignment_flow_simulation(tmp_path,backend,mutant):
    if not shutil.which('yosys') or not shutil.which('iverilog' if backend=='icarus' else 'verilator'):
        pytest.skip('Yosys and native simulator required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,input [7:0] data,output reg [7:0] q=0); '
                      'always @(posedge clk) q<=data+'+('2' if mutant else '1')+'; '
                      'property p; logic [7:0] v; @(posedge clk) (1,v=data,v=v+1) |=> q==v; endproperty '
                      'a: assert property(p); endmodule')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(clk='0',data='11111111')),dict(time=1,inputs=dict(clk='1')),
        dict(time=2,inputs=dict(clk='0')),dict(time=3,inputs=dict(data='00000000')),
        dict(time=4,inputs=dict(clk='1')),dict(time=5,inputs=dict(clk='0')),
        dict(time=6,inputs=dict(data='00000001')),dict(time=7,inputs=dict(clk='1')),
    ])))
    out=tmp_path/'out'
    run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                  backend=backend,observe=None,check_x=False,timeout=60))
    result=load_run(out)
    assert result.status==('assert' if mutant else 'pass'),result.to_dict()
    assert result.extra['assertions'][0]['passed']==(0 if mutant else 2)
    assert result.extra['assertions'][0]['failed']==(2 if mutant else 0)
