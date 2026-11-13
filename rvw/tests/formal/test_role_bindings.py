import json
import shutil
from pathlib import Path
import pytest
from rvw.formal.role_bindings import bind
from rvw.formal.apps import generate, flow


def plan():
    ports={n:{'direction':d,'width':w} for n,d,w in [
        ('clk','input',1),('reset','input',1),('av','input',1),('ar','output',1),('ad','input',2),
        ('bv','input',1),('br','output',1),('bd','input',2),('ov','output',1),('orr','input',1),('od','output',2)]}
    channels=[dict(valid=v,ready=r,payload=d) for v,r,d in [('av','ar','ad'),('bv','br','bd'),('ov','orr','od')]]
    return dict(top='top',clock='clk',reset='reset',ports=ports),channels


def test_arbiter_and_fifo_structural_binding():
    p,channels=plan()
    prop=bind('arbiter',channels,[],p['ports'],1)
    assert prop['kind']=='arbiter_transfer'
    assert 'rvwa_accept' in generate(p,prop)
    fifo=bind('fifo',[channels[0],channels[2]],[(1,2,2)],p['ports'],1)
    assert fifo['capacity']==2
    assert 'rvwa_queue' in generate(p,fifo)
    assert bind('fifo',[channels[0],channels[2]],[],p['ports'],1) is None


@pytest.mark.parametrize('mutant,expected',[(False,'pass'),(True,'fail')])
def test_native_arbiter_transfer(tmp_path,mutant,expected):
    if not all(shutil.which(t) for t in ('yosys','sby')):
        pytest.skip('native Yosys/SBY required')
    p,channels=plan(); prop=bind('arbiter',channels,[],p['ports'],1)
    source=tmp_path/'top.v'
    source.write_text('module top(input clk,reset,av,bv,orr,input [1:0] ad,bd,output ar,br,ov,output [1:0] od);\n'
        'assign ar=orr; assign br='+('orr' if mutant else 'orr && !av')+'; assign ov=av||bv; assign od=av?ad:bd; endmodule')
    wrapper=tmp_path/'wrapper.sv';wrapper.write_text(generate(p,prop))
    result=flow([source,wrapper],'rvwa_top','clk','reset',tmp_path/'proof',8,'abc:pdr',15,'prove')
    assert result['status']==expected


def test_counter_wrap_is_an_observation():
    from rvw.formal.automonitors import observation
    assert observation('counter_wrap',{'status':'fail','proof_kind':'bounded'})=='reached'
    assert observation('counter_wrap',{'status':'pass','proof_kind':'unbounded'})=='unreachable_conditional'
