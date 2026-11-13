import json
import shutil
import pytest
from rvw.cli import main
from rvw.formal.blackbox_models import load


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','eqy','sby','yosys-abc')),reason='needs native equivalence tools')
@pytest.mark.parametrize('mutant',[False,True])
def test_blackbox_contract_never_earns_unconditional_equivalence(tmp_path,mutant):
    gold,gate=tmp_path/'gold.v',tmp_path/'gate.v'
    text='(* blackbox *) module Primitive(input [3:0] a,output [3:0] y);endmodule\nmodule Top(input clk,input [3:0] a,output [3:0] q);wire [3:0] y;Primitive p(a,y);assign q=EXPR;endmodule'
    gold.write_text(text.replace('EXPR','y'));gate.write_text(text.replace('EXPR','y^1' if mutant else 'y'))
    model=tmp_path/'primitive.v';model.write_text('module Primitive(input [3:0] a,output [3:0] y);assign y=a+1;endmodule')
    contract=tmp_path/'contract.json';contract.write_text(json.dumps({'schema':'rvw.equiv-blackbox/1','models':['primitive.v'],
        'obligations':['The physical Primitive implements the supplied behavior.']}))
    out=tmp_path/'out'
    rc=main(['formal','equiv','--gold',str(gold),'--gate',str(gate),'--top','Top','--blackbox-contract',str(contract),'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='conditional',result
    assert result['contract_verdict']==('not_equivalent' if mutant else 'equivalent'),result
    assert rc==1
    assert result['blackbox_contract']['manifest_sha256']
    assert result['inputs'][0]['input_snapshot']['files'][-1]['sha256']==result['blackbox_contract']['models'][0]['sha256']


def test_contract_requires_explicit_obligations_and_sources(tmp_path):
    out=tmp_path/'out';out.mkdir();contract=tmp_path/'contract.json'
    contract.write_text(json.dumps({'schema':'rvw.equiv-blackbox/1','models':[]}))
    with pytest.raises(ValueError,match='obligations'):load(contract,out)
    contract.write_text(json.dumps({'schema':'rvw.equiv-blackbox/1','models':[],'obligations':['unproved model relation']}))
    with pytest.raises(ValueError,match='source paths'):load(contract,out)


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','eqy','sby','yosys-abc')),reason='needs native equivalence tools')
def test_model_assumption_cannot_earn_conditional_proof(tmp_path):
    rtl=tmp_path/'top.v';rtl.write_text('(* blackbox *) module Primitive(input a,output y);endmodule\nmodule Top(input clk,a,output q);Primitive p(a,q);endmodule')
    (tmp_path/'model.v').write_text('module Primitive(input a,output y);assign y=a;always @* assume(0);endmodule')
    manifest=tmp_path/'contract.json';manifest.write_text(json.dumps({'schema':'rvw.equiv-blackbox/1','models':['model.v'],'obligations':['unproved implementation relation']}))
    out=tmp_path/'out'
    main(['formal','equiv','--gold',str(rtl),'--gate',str(rtl),'--top','Top','--blackbox-contract',str(manifest),'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='inconclusive' and 'contract_verdict' not in result,result


def test_equiv_mcp_preserves_source_lists_and_verdicts(tmp_path):
    from rvw.formal.mcp_tools import _argv,_runner,mcp_tools
    from rvw.mcp.spec import ToolError
    argv=_argv('equiv',{'gold':['a.v','model.v'],'gate':['b.v'],'blackbox_contract':'c.json','dsec':True})
    assert argv[5:8]==['--gold','a.v','model.v'] and '--dsec' in argv
    assert 'formal_equiv' in {t.name for t in mcp_tools()}
    class Job:
        def __init__(self,status,code):self.status=status;self.code=code
        def run(self,argv):
            (tmp_path/'result.json').write_text(json.dumps({'status':self.status}));return self.code
        def tail(self,n):return ''
    assert _runner('equiv')(Job('equivalent',0),out=str(tmp_path))['status']=='equivalent'
    assert _runner('equiv')(Job('conditional',1),out=str(tmp_path))['status']=='conditional'
    with pytest.raises(ToolError):_runner('equiv')(Job('conditional',0),out=str(tmp_path))
