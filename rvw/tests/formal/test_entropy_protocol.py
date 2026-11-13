import json
import shutil
import pytest
from rvw.cli import main
from rvw.formal.apps import generate


def plan():
    ports={n:{'direction':'input','width':1} for n in ('clk','reset','access','write','allowed','refill','fatal')}
    ports.update({'entropy':{'direction':'input','width':16},'seed':{'direction':'output','width':32},'illegal':{'direction':'output','width':1}})
    prop={'id':'seed_protocol','kind':'entropy',**{n:n for n in ('seed','access','write','allowed','illegal','refill','fatal')}}
    return {'schema':'rvw.formal-apps/1','top':'Seed','clock':'clk','reset':'reset','verilog':['dut.v'],'ports':ports,'properties':[prop]}


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','sby','yosys-abc')),reason='needs native formal tools')
@pytest.mark.parametrize('mutant',['none','wipe','dead','illegal','mask'])
def test_seed_protocol_and_failure_mutants(tmp_path,mutant):
    p=plan()
    illegal='0' if mutant=='illegal' else '(access && !(write && allowed))'
    word='data' if mutant=='mask' else "(state==2 ? data : 16'b0)"
    wipe='' if mutant=='wipe' else 'else if(poll && state==2) begin state<=1;data<=0;end'
    dead='0' if mutant=='dead' else 'state==3'
    rtl='module Seed(input clk,reset,access,write,allowed,refill,fatal,input [15:0] entropy,output [31:0] seed,output illegal); '
    rtl += f'assign illegal={illegal};wire poll=access && write && allowed && !illegal;reg [1:0] state; reg [15:0] data; assign seed={{state,14\'b0,{word}}}; '
    rtl += f'always @(posedge clk) begin if(reset) begin state<=0;data<=0;end else if(fatal || {dead}) begin state<=3;data<=0;end '
    rtl += 'else if(state==0 && !poll) begin state<=0;data<=0;end '
    rtl += 'else if(refill) begin state<=2;data<=entropy;end '+wipe+' else if(state==0 && poll) begin state<=1;data<=0;end end endmodule'
    # In the mask mutant, retain stale data after a poll so it is visible in WAIT.
    if mutant=='mask':rtl=rtl.replace('state<=1;data<=0;end else if(state==0', 'state<=1;end else if(state==0')
    (tmp_path/'dut.v').write_text(rtl)
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','apps',str(manifest),'--out',str(out),'--mode','prove','--engine','abc:pdr','--timeout','60'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('pass' if mutant=='none' else 'fail'),result


def test_entropy_binding_requires_declared_widths():
    p=plan();p['ports']['seed']['width']=16
    with pytest.raises(ValueError,match='seed needs'):generate(p,p['properties'][0])
