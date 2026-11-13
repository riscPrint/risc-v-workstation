import json
import shutil
import pytest
from rvw.formal.security.pair import proof_settings


@pytest.mark.fast
@pytest.mark.parametrize('plan',[{'mode':'unknown'},{'depth':0},{'depth':129},{'depth':True}])
def test_invalid_pair_bounds(plan):
    with pytest.raises(ValueError):proof_settings(plan)


@pytest.mark.fast
def test_pair_proof_defaults_and_bounds():
    assert proof_settings({})==('prove',20,'abc:pdr')
    assert proof_settings({'mode':'bmc','depth':4})==('bmc',4,'smtbmc:yices')


@pytest.mark.slow
@pytest.mark.skipif(not all(shutil.which(x) for x in ('yosys','sby','yices-smt2')),reason='native formal tools')
def test_bounded_initialization_marks_proof_scope(tmp_path):
    from rvw.cli import main
    (tmp_path/'dut.v').write_text('module Unit(input clk,reset,a,output reg q); always @(posedge clk) if(reset) q<=0; else q<=a; endmodule')
    plan={'schema':'rvw.security-pair/1','kind':'initialization','mode':'bmc','depth':4,
          'rtl':'dut.v','top':'Unit','clock':'clk','reset':'reset',
          'ports':{n:{'direction':d,'width':1} for n,d in [('clk','input'),('reset','input'),('a','input'),('q','output')]},
          'observations':['q'],'adversary':'controls shared inputs','unmodeled_channels':['analog'],
          'reset_values':{'q':0}}
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    assert main(['formal','security','pair','--manifest',str(tmp_path/'plan.json'),'--out',str(tmp_path/'proof')])==0
    result=json.loads((tmp_path/'proof/result.json').read_text())
    assert result['status']=='pass' and result['proof_kind']=='bounded' and result['depth']==4
    assert 'bounded' in result['reset_coverage']['scope']
