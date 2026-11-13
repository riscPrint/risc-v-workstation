from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


@pytest.mark.parametrize('overlap',[False,True])
@pytest.mark.parametrize('coincident',[False,True])
@pytest.mark.parametrize('mutant',[False,True])
def test_native_two_clock_implication(tmp_path,overlap,coincident,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    operator='|->' if overlap else '|=>'
    source.write_text('module m(input a,b,req,ack,output q); assign q=ack; '
                      'p: assert property (@(posedge a) req '+operator+' @(posedge b) ack); '
                      'c: cover property (@(posedge a) req '+operator+' @(posedge b) ack); endmodule')
    rows=[dict(time=0,inputs=dict(a='0',b='0',req='1',ack='0' if mutant else '1')),
          dict(time=1,inputs=dict(a='1',**({'b':'1'} if coincident else {}))),
          dict(time=2,inputs=dict(a='0',b='0')),
          dict(time=3,inputs=dict(a='1')),
          dict(time=4,inputs=dict(a='0')),
          dict(time=5,inputs=dict(req='0')),
          dict(time=6,inputs=dict(b='1'))]
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=rows)))
    out=tmp_path/'out'
    code=run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                       backend='icarus',observe=None,check_x=False,timeout=30))
    result=load_run(out)
    assert code==int(mutant) and result.status==('assert' if mutant else 'pass'),result.to_dict()
    counts={p['id']:p for p in result.extra['assertions']}
    assert counts['p']['passed']==(0 if mutant else 2)
    assert counts['p']['failed']==(2 if mutant else 0)
    assert counts['c']['covered']==(0 if mutant else 2)
    assert counts['c']['missed']==(2 if mutant else 0)
    assert len(result.extra['cross_clock_properties'])==2


@pytest.mark.parametrize('overlap',[False,True])
def test_native_coincident_event_strength(tmp_path,overlap):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input a,b,req,ack,output q); assign q=ack; '
                      'p: assert property (@(posedge a) req '+('|->' if overlap else '|=>')+' @(posedge b) ack); endmodule')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(a='0',b='0',req='1',ack='0')),
        dict(time=1,inputs=dict(a='1',b='1')),
        dict(time=2,inputs=dict(a='0',b='0')),
        dict(time=3,inputs=dict(ack='1',req='0')),
        dict(time=4,inputs=dict(b='1')),
    ])))
    out=tmp_path/'out'
    run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                  backend='icarus',observe=None,check_x=False,timeout=30))
    result=load_run(out)
    assert result.status==('assert' if overlap else 'pass'),result.to_dict()
    assert result.extra['assertions'][0]['failed']==int(overlap)
    assert result.extra['assertions'][0]['passed']==int(not overlap)


def test_native_falling_clock_events(tmp_path):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input a,b,req,ack,output q); assign q=ack; '
                      'p: assert property (@(negedge a) req |=> @(negedge b) ack); endmodule')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(a='1',b='1',req='1',ack='1')),
        dict(time=1,inputs=dict(a='0')),dict(time=2,inputs=dict(a='1')),
        dict(time=3,inputs=dict(req='0')),dict(time=4,inputs=dict(b='0')),
    ])))
    out=tmp_path/'out'
    assert run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                         backend='icarus',observe=None,check_x=False,timeout=30))==0
    assert load_run(out).extra['assertions'][0]['passed']==1


@pytest.mark.parametrize('req,ack,target,status,failed',[
    ('0','1',True,'error',0), ('x','1',True,'error',0),
    ('1','x',True,'assert',1), ('1','1',False,'error',0),
])
def test_native_unknown_and_pending_attempts(tmp_path,req,ack,target,status,failed):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input a,b,req,ack,output q); assign q=ack; '
                      'p: assert property (@(posedge a) req |=> @(posedge b) ack); endmodule')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(a='0',b='0',req=req,ack=ack)),
        dict(time=1,inputs=dict(a='1')),dict(time=2,inputs=dict(b='1' if target else '0')),
    ])))
    out=tmp_path/'out'
    run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                  backend='icarus',observe=None,check_x=False,timeout=30))
    result=load_run(out)
    assert result.status==status,result.to_dict()
    assert result.extra['assertions'][0]['failed']==failed
    assert result.extra['assertions'][0]['passed']==0
    if status=='error':
        assert result.extra['inconclusive']=='no_checks'
