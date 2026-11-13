from argparse import Namespace
import json
import shutil
import subprocess

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


RTL='''module leaf(input clk,rst,d,output reg q=0,output reg divided=0);
always @(posedge clk) if(rst)divided<=0; else divided<=!divided;
always @(posedge divided or posedge rst) if(rst)q<=0; else q<=d;
endmodule
module m(input a,b,rst,d,output qa,qb);
wire da,db; leaf left(a,rst,d,qa,da); leaf right(b,rst,d,qb,db);
endmodule'''


def capture(tmp_path,rtl=RTL,bench=None):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    source.write_text(rtl)
    bench=bench or '''module capture;
reg a=0,b=0,rst=0,d=1'bx; wire qa,qb; m dut(a,b,rst,d,qa,qb);
initial begin $dumpfile("state.vcd"); $dumpvars(0,capture);
#1;a=1; #1;a=0; d=1; #1;b=1; #1;b=0; #1;$finish; end endmodule'''
    (tmp_path/'capture.sv').write_text(bench)
    compiled=subprocess.run(['nice','-n','10','iverilog','-g2012','-s','capture','-o','capture.vvp','m.sv','capture.sv'],
                            cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert compiled.returncode==0,compiled.stderr
    result=subprocess.run(['nice','-n','10','vvp','capture.vvp'],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return source


def replay(tmp_path,source,registers,inputs=None,rows=None):
    events=tmp_path/'events.json'
    inputs=inputs or dict(a='0',b='0',rst='0',d='1')
    rows=rows or [dict(time=0,inputs=inputs),dict(time=1,inputs=dict(rst='1')),
                 dict(time=2,inputs=dict(rst='0')),dict(time=3,inputs=dict(a='1')),
                 dict(time=4,inputs=dict(a='0')),dict(time=5,inputs=dict(a='1'))]
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',clocks=[name for name in ('a','b') if name in inputs],
                                     state=dict(trace='state.vcd',time=5,scope='capture.dut',registers=registers),events=rows)))
    out=tmp_path/'out'
    code=run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                       backend='icarus',observe=None,check_x=True,timeout=30))
    return code,load_run(out)


@pytest.mark.parametrize('reverse_order',[False,True])
def test_native_hierarchy_and_derived_clock_state(tmp_path,reverse_order):
    source=capture(tmp_path)
    registers=['left.divided','left.q','right.divided','right.q']
    if reverse_order:
        registers.reverse()
    code,result=replay(tmp_path,source,registers)
    assert code==1 and result.status=='fail',result.to_dict()
    assert result.extra['state_load']['state_bits']==4
    values={(row['time'],row['signal']):row['value'] for row in result.extra['observations']}
    assert values[0,'qa']=='x' # Setup must not erase the trace's X on the derived-clock event.
    assert values[0,'qb']=='1'
    assert values[1,'qa']==values[1,'qb']=='0' # Async reset between source-clock edges.
    assert values[3,'qa']=='0'
    assert values[5,'qa']=='1' # A later derived edge resolves the unknown state.


def test_partial_child_state_refused(tmp_path):
    source=capture(tmp_path)
    with pytest.raises(ValueError,match='incomplete trace register state'):
        replay(tmp_path,source,['left.divided','left.q'])


def test_combinational_reg_alias_is_not_loaded_as_flop(tmp_path):
    rtl='''module m(input clk,d,output reg aliasq); reg q=0;
always @(posedge clk)q<=d; always @*aliasq=q; endmodule'''
    bench='''module capture; reg clk=0,d=1; wire aliasq; m dut(clk,d,aliasq);
initial begin $dumpfile("state.vcd"); $dumpvars(0,capture);
#1;clk=1; #1;clk=0; #3;$finish; end endmodule'''
    source=capture(tmp_path,rtl,bench)
    rows=[dict(time=0,inputs=dict(clk='0',d='1')),dict(time=1,inputs=dict(clk='1'))]
    with pytest.raises(ValueError,match='does not map to DUT register bits'):
        replay(tmp_path,source,['aliasq'],dict(clk='0',d='1'),rows)
    code,result=replay(tmp_path,source,['q'],dict(clk='0',d='1'),rows)
    assert code==0 and result.status=='pass',result.to_dict()
    assert result.extra['observations'][0]['value']=='1'
