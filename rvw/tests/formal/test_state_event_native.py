from argparse import Namespace
import json
import shutil
import subprocess

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


RTL='''module m(input a,b,rst,d, output reg qa=0, output reg qb=0);
always @(posedge a or posedge rst) if(rst) qa<=0; else qa<=d;
always @(posedge b) qb<=d;
endmodule'''


def trace(tmp_path,unknown=False):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    dut=tmp_path/'m.sv'
    dut.write_text(RTL)
    bench=tmp_path/'capture.sv'
    bench.write_text('module capture; reg a=0,b=0,rst=0,d=1; wire qa,qb; m dut(a,b,rst,d,qa,qb); '
                     'initial begin $dumpfile("state.vcd"); $dumpvars(0,capture); '
                     '#1;a=1; #1;a=0; d='+('1\'bx' if unknown else '1')+'; '
                     '#1;b=1; #1;b=0; d=1; #1;$finish; end endmodule')
    result=subprocess.run(['nice','-n','10','iverilog','-g2012','-s','capture','-o','capture.vvp',str(dut),str(bench)],
                          cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    result=subprocess.run(['nice','-n','10','vvp','capture.vvp'],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return dut


def spec(tmp_path,registers=('qa','qb'),**kw):
    events=tmp_path/'events.json'
    data=dict(schema='rvw.formal-events/1',clocks=['a','b'],state=dict(trace='state.vcd',time=5,scope='capture.dut',registers=list(registers)),events=[
        dict(time=0,inputs=dict(a='0',b='0',rst='0',d='1')),
        dict(time=1,inputs=dict(rst='1')),
        dict(time=2,inputs=dict(rst='0')),
        dict(time=3,inputs=dict(b='1')),
        dict(time=4,inputs=dict(b='0')),
    ])
    data['state'].update(kw)
    events.write_text(json.dumps(data))
    return events


def replay(tmp_path,dut,events):
    out=tmp_path/'out'
    code=run(Namespace(verilog=[str(dut)],top='m',events=str(events),out=str(out),
                       backend='icarus',observe=None,check_x=True,timeout=30))
    return code,load_run(out)


@pytest.mark.parametrize('unknown',[False,True])
def test_native_multiclock_state_and_async_reset(tmp_path,unknown):
    dut=trace(tmp_path,unknown)
    code,result=replay(tmp_path,dut,spec(tmp_path))
    assert result.status==('fail' if unknown else 'pass'),result.to_dict()
    assert code==int(unknown)
    assert result.extra['state_load']['state_bits']==2
    observations={(row['time'],row['signal']):row['value'] for row in result.extra['observations']}
    assert observations[0,'qa']=='1' # RTL init would be zero without state load.
    assert observations[0,'qb']==('x' if unknown else '1')
    assert observations[1,'qa']=='0' # Asynchronous reset pulse, without a clock edge.
    assert observations[3,'qb']=='1' # Other clock resolves the trace's unknown state.
    assert len(result.extra['event_capture']['files'])==2


def test_partial_state_refused(tmp_path):
    dut=trace(tmp_path)
    with pytest.raises(ValueError,match='incomplete trace register state'):
        replay(tmp_path,dut,spec(tmp_path,('qa',)))


def test_input_phase_must_match_trace(tmp_path):
    dut=trace(tmp_path)
    events=spec(tmp_path)
    data=json.loads(events.read_text())
    data['events'][0]['inputs']['a']='1'
    events.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='initial event inputs disagree'):
        replay(tmp_path,dut,events)


def test_fst_state_decoder_reads_captured_copy(tmp_path):
    if not all(shutil.which(tool) for tool in ('vcd2fst','fst2vcd')):
        pytest.skip('GTKWave converters required')
    dut=trace(tmp_path)
    result=subprocess.run(['nice','-n','10','vcd2fst','state.vcd','state.fst'],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    code,result=replay(tmp_path,dut,spec(tmp_path,trace='state.fst'))
    assert code==0 and result.extra['state_load']['state_bits']==2


def test_loaded_state_starts_new_monitor_histories(tmp_path):
    dut=trace(tmp_path)
    dut.write_text(RTL.replace('endmodule','p: assert property (@(posedge b) qa); endmodule'))
    code,result=replay(tmp_path,dut,spec(tmp_path))
    # qa has been cleared by the async reset before b fires. The finite assertion
    # must use the loaded continuation, not an initialization sample.
    assert code==1 and result.status=='assert',result.to_dict()
    assert result.extra['assertions'][0]['failed']==1
    assert result.extra['assertions'][0]['passed']==0


def test_state_replay_high_initial_clock_has_no_bootstrap_check(tmp_path):
    dut=trace(tmp_path)
    # Use the state at timestamp 1, with a high. Both registers are traced.
    dut.write_text(RTL.replace('endmodule','p: assert property (@(posedge a) qa); endmodule'))
    events=spec(tmp_path,time=1)
    data=json.loads(events.read_text())
    data['events'][0]['inputs']['a']='1'
    data['events'][1:]=[dict(time=1,inputs=dict(a='0')),dict(time=2,inputs=dict(a='1'))]
    events.write_text(json.dumps(data))
    code,result=replay(tmp_path,dut,events)
    assert code==0,result.to_dict()
    assert result.extra['assertions'][0]['passed']==1
    assert result.extra['assertions'][0]['failed']==0
