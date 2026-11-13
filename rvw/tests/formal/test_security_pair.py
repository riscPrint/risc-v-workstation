import json
import shutil
import pytest
from rvw.cli import main
from rvw.formal.security.pair import generate

TOOLS=all(shutil.which(t) for t in ('yosys','sby','yosys-abc'))


def plan(rtl='dut.v'):
    return {'schema':'rvw.security-pair/1','top':'Unit','rtl':rtl,'clock':'clk','reset':'reset',
            'ports':{'clk':{'direction':'input','width':1},'reset':{'direction':'input','width':1},
                     'secret':{'direction':'input','width':1},'public':{'direction':'input','width':1},
                     'arch':{'direction':'output','width':1},'cache':{'direction':'output','width':1}},
            'secrets':['secret'],'architectural':['arch'],'observations':['cache'],
            'adversary':'controls secret and public input data','unmodeled_channels':['power','analog noise']}


@pytest.mark.skipif(not TOOLS,reason='needs native formal tools')
@pytest.mark.parametrize('leak,declassify,expected',[(False,False,'pass'),(True,False,'fail'),(True,True,'pass')])
def test_prefix_security_contract(tmp_path,leak,declassify,expected):
    p=plan();rtl=tmp_path/'dut.v'
    rtl.write_text('module Unit(input clk,reset,secret,public,output reg arch,cache); always @(posedge clk) begin '
                   f'if(reset) begin arch<=0;cache<=0;end else begin arch<={"secret" if declassify else "public"};cache<={"secret" if leak else "public"};end end endmodule')
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','security','pair','--manifest',str(manifest),'--out',str(out),'--timeout','60'])
    result=json.loads((out/'result.json').read_text());assert result['status']==expected,result


@pytest.mark.skipif(not TOOLS,reason='needs native formal tools')
@pytest.mark.parametrize('reset_state,expected',[(True,'pass'),(False,'fail')])
def test_uninitialized_state_reaches_output(tmp_path,reset_state,expected):
    p=plan();p['kind']='initialization';p['secrets']=[];p['architectural']=[]
    rtl=tmp_path/'dut.v'
    rtl.write_text('module Unit(input clk,reset,secret,public,output arch,cache); reg state; '
                   f'always @(posedge clk) {"if(reset) state<=0; else " if reset_state else ""}if(public) state<=secret; '
                   'assign arch=0;assign cache=state;endmodule')
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','security','pair','--manifest',str(manifest),'--out',str(out),'--timeout','60'])
    result=json.loads((out/'result.json').read_text());assert result['status']==expected,result


def test_refuse_vacuous_or_private_clock_contracts():
    p=plan();p['observations']=['arch']
    with pytest.raises(ValueError):generate(p)
    p=plan();p['secrets']=['clk']
    with pytest.raises(ValueError):generate(p)


@pytest.mark.skipif(not TOOLS,reason='needs native formal tools')
def test_embedded_assumption_cannot_hide_leak(tmp_path):
    p=plan();(tmp_path/'dut.v').write_text('module Unit(input clk,reset,secret,public,output arch,cache);assign arch=0;assign cache=secret;always @* assume(0);endmodule')
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','security','pair','--manifest',str(manifest),'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='inconclusive' and 'formal properties' in result['reason'],result


def test_mcp_nested_command():
    from rvw.formal.mcp_tools import _argv
    argv=_argv('security pair',{'manifest':'p.json','out':'run'})
    assert argv[3:6]==['formal','security','pair']


@pytest.mark.skipif(not TOOLS,reason='needs native formal tools')
@pytest.mark.parametrize('expected_value,expected_status',[(0,'pass'),(1,'fail')])
def test_declared_reset_value_coverage(tmp_path,expected_value,expected_status):
    p=plan();p['kind']='initialization';p['secrets']=[];p['architectural']=[];p['reset_values']={'cache':expected_value}
    (tmp_path/'dut.v').write_text('module Unit(input clk,reset,secret,public,output arch,output reg cache); assign arch=0; always @(posedge clk) if(reset)cache<=0;else cache<=public;endmodule')
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','security','pair','--manifest',str(manifest),'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==expected_status,result
    assert result['reset_coverage']['declared_bits']==1
    assert result['reset_coverage']['output_bits']==2
    assert result['reset_coverage']['proved_bits']==(1 if expected_status=='pass' else 0)


@pytest.mark.skipif(not TOOLS,reason='needs native formal tools')
@pytest.mark.parametrize('leak',[False,True])
def test_declared_zkt_unit_timing_output(tmp_path,leak):
    p=plan();p['kind']='constant_time';p['architectural']=[];p['operations']=['sha256sig0']
    (tmp_path/'dut.v').write_text('module Unit(input clk,reset,secret,public,output arch,cache); assign arch=secret;assign cache='+('secret' if leak else 'public')+';endmodule')
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','security','pair','--manifest',str(manifest),'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('fail' if leak else 'pass'),result
