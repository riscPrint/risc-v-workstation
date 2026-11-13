from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


def replay(tmp_path,backend,expression,rows,clocks=None):
    needed=('yosys','iverilog','vvp') if backend=='icarus' else ('yosys','verilator')
    if not all(shutil.which(tool) for tool in needed):
        pytest.skip('Yosys and selected native simulator required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,rst,req,hold,response,output q); assign q=response; '
                      'p: assert property (@(posedge clk) disable iff(rst) '+expression+'); endmodule')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=rows,clocks=clocks or [])))
    out=tmp_path/'out'
    code=run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                       backend=backend,observe=None,check_x=False,timeout=60))
    return code,load_run(out)


@pytest.mark.parametrize('backend',['icarus','verilator'])
@pytest.mark.parametrize('nonoverlap',[False,True])
def test_native_cancel_and_restart(tmp_path,backend,nonoverlap):
    rows=[dict(time=0,inputs=dict(clk='0',rst='0',req='1',hold='1',response='0')),
          dict(time=1,inputs=dict(clk='1')),dict(time=2,inputs=dict(clk='0')),
          dict(time=4,inputs=dict(clk='1')),dict(time=5,inputs=dict(clk='0')),
          dict(time=6,inputs=dict(rst='1')),dict(time=7,inputs=dict(rst='0')),
          dict(time=8,inputs=dict(response='1')),dict(time=9,inputs=dict(clk='1')),
          dict(time=10,inputs=dict(clk='0')),dict(time=11,inputs=dict(req='0')),
          dict(time=12,inputs=dict(clk='1'))]
    code,result=replay(tmp_path,backend,'req '+('|=>' if nonoverlap else '|->')+' s_eventually response',rows)
    assert code==0 and result.status=='pass',result.to_dict()
    check=result.extra['assertions'][0]
    assert check['passed']==1 and check['failed']==0 and check['pending']==0
    assert check['cancelled']==2


@pytest.mark.parametrize('backend',['icarus','verilator'])
def test_native_cancel_does_not_erase_failure(tmp_path,backend):
    rows=[dict(time=0,inputs=dict(clk='0',rst='0',req='1',hold='0',response='0')),
          dict(time=1,inputs=dict(clk='1')),dict(time=2,inputs=dict(clk='0')),
          dict(time=3,inputs=dict(rst='1')),dict(time=4,inputs=dict(rst='0',req='0'))]
    _,result=replay(tmp_path,backend,'req |-> hold s_until response',rows)
    assert result.status=='assert',result.to_dict()
    assert result.extra['assertions'][0]['failed']==1


@pytest.mark.parametrize('unknown',['x','z'])
@pytest.mark.parametrize('expression',['0','1 |=> 0'])
def test_unknown_disable_does_not_hide_finite_fault(tmp_path,expression,unknown):
    rows=[dict(time=0,inputs=dict(clk='0',rst=unknown,req='0',hold='1',response='0')),
          dict(time=1,inputs=dict(clk='1')),dict(time=2,inputs=dict(clk='0')),
          dict(time=3,inputs=dict(clk='1'))]
    _,result=replay(tmp_path,'icarus',expression,rows)
    assert result.status=='assert',result.to_dict()
    assert result.extra['assertions'][0]['failed']>=1


@pytest.mark.parametrize('unknown',['x','z'])
def test_unknown_disable_does_not_cancel_unbounded(tmp_path,unknown):
    rows=[dict(time=0,inputs=dict(clk='0',rst='0',req='1',hold='1',response='0')),
          dict(time=1,inputs=dict(clk='1')),dict(time=2,inputs=dict(clk='0')),
          dict(time=3,inputs=dict(rst=unknown,req='0',response='1')),
          dict(time=4,inputs=dict(clk='1'))]
    _,result=replay(tmp_path,'icarus','req |-> s_eventually response',rows)
    assert result.status=='pass',result.to_dict()
    check=result.extra['assertions'][0]
    assert check['passed']==1 and check['cancelled']==0



def test_same_timestamp_control_is_refused_even_when_declared_as_clock(tmp_path):
    rows=[dict(time=0,inputs=dict(clk='0',rst='0',req='1',hold='1',response='0')),
          dict(time=1,inputs=dict(clk='1',rst='1'))]
    with pytest.raises(ValueError,match='native_disable_timestamp'):
        replay(tmp_path,'icarus','req |-> s_eventually response',rows,clocks=['clk','rst'])
