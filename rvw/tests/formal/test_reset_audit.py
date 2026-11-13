import json
import shutil

import pytest
from rvw.cli import main
from rvw.formal.reset_audit import ZERO,ONE,FREE,transfer


@pytest.mark.fast
def test_abstract_controlling_values_and_mux_selection():
    stale=(3,frozenset({27}))
    assert transfer('$_AND_',[ZERO,stale])==ZERO
    assert transfer('$_OR_',[ONE,stale])==ONE
    assert transfer('$_MUX_',[FREE,stale,ZERO])==FREE
    assert transfer('$_MUX_',[ZERO,stale,ONE])==stale
    assert transfer('$_MUX_',[ONE,ONE,stale])==ONE
    assert transfer('$_XOR_',[stale,stale])==stale  # Conservative reconvergence.


@pytest.mark.skipif(not shutil.which('yosys'),reason='needs Yosys')
@pytest.mark.parametrize('active',['high','low'])
def test_reset_constants_and_uninitialised_output_paths(tmp_path, active):
    rtl=tmp_path/'dut.v';condition='reset' if active=='high' else '!reset'
    rtl.write_text('''module Unit(input clk,reset,input [3:0] a,output [3:0] q,output leak,safe);
reg [3:0] fixed;reg stale,valid;
always @(posedge clk) begin
 if ('''+condition+''') begin fixed<=9;valid<=0;end
 else begin fixed<=a;valid<=1;stale<=a[0];end
end
assign q=fixed;assign leak=stale;assign safe=valid ? stale : 1'b0;
endmodule''')
    out=tmp_path/'out'
    rc=main(['formal','reset-audit','--rtl',str(rtl),'--top','Unit','--reset','reset','--reset-active',active,
        '--cycles','2','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert rc==1 and result['status']=='inconclusive' and result['analysis_status']=='complete',result
    assert result['reset_coverage']=={'retained_register_bits':6,'constant_reset_bits':5,'nonconstant_reset_bits':1,'bits_with_initial_dependencies':1}
    fixed=next(row for row in result['registers'] if row['name'] in ('fixed','q'))
    assert [bit['reset_value'] for bit in fixed['bits']]==[1,0,0,1]
    before,after,last=result['output_influence']
    assert before['outputs']['leak'][0]['initial_dependencies']
    assert not before['outputs']['safe'][0]['initial_dependencies']
    assert not after['outputs']['leak'][0]['initial_dependencies']
    assert not last['outputs']['leak'][0]['initial_dependencies']


@pytest.mark.skipif(not shutil.which('yosys'),reason='needs Yosys')
@pytest.mark.parametrize('kind',['literal','data'])
def test_nonconstant_reset_value_is_not_counted_as_constant(tmp_path, kind):
    rtl=tmp_path/'dut.v'
    rtl.write_text('module Unit(input clk,reset,a,output reg q);always @(posedge clk) q<=reset ? '+
        ("1'bx" if kind=='literal' else 'a')+':q;endmodule')
    out=tmp_path/'out';main(['formal','reset-audit','--rtl',str(rtl),'--top','Unit','--reset','reset','--out',str(out)])
    result=json.loads((out/'result.json').read_text());assert result['analysis_status']=='complete',result
    assert result['reset_coverage']['constant_reset_bits']==0
    assert result['reset_coverage']['bits_with_initial_dependencies']==0
    assert result['output_influence'][0]['outputs']['q'][0]['literal_xz']==(kind=='literal')


@pytest.mark.skipif(not shutil.which('yosys'),reason='needs Yosys')
@pytest.mark.parametrize('kind',['clock','latch','assumption','init'])
def test_unsupported_reset_models_remain_incomplete(tmp_path, kind):
    text='module Unit(input clk,reset,a,output reg q);always @(posedge clk) q<=reset ? 0 : a;endmodule'
    if kind=='clock':text=text.replace('posedge clk','posedge a')
    if kind=='latch':text='module Unit(input clk,reset,a,output reg q);always @* if(reset)q=a;endmodule'
    if kind=='assumption':text=text.replace('endmodule','always @* assume(a);endmodule')
    if kind=='init':text=text.replace('always @(posedge','initial q=0;always @(posedge')
    rtl=tmp_path/'dut.v';rtl.write_text(text);out=tmp_path/'out'
    main(['formal','reset-audit','--rtl',str(rtl),'--top','Unit','--reset','reset','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='inconclusive' and result['analysis_status']=='incomplete',result
    assert result['reason']
