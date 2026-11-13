import pytest
from rvw.formal.cell_model import query
from rvw.formal.cores import prepare


def module():
    return {'cells': {'not': {'type':'$_NOT_','connections':{'A':[2],'Y':[3]}},
        'assert': {'type':'$assert','connections':{'A':[3],'EN':['1']}}}, 'netnames':{}}


def test_each_cell_equation_is_named():
    text, binding = query(module(),'top',3)
    _, assertions = prepare(text)
    assert set(assertions) == set(binding['constraints'])
    assert len(binding['logic']) == 1
    assert {b['sample'] for b in binding['constraints'].values() if b['kind']=='cell'} == {0,1,2}


def test_unknown_cells_fail_closed():
    m=module(); m['cells']['not']['type']='custom'
    with pytest.raises(ValueError,match='unsupported Boolean cell'):
        query(m,'top',2)


def test_requirement_missing_property_and_bounded_pass():
    from rvw.formal.testplan import requirement_obligations
    plan={'requirements':[{'requirement_id':'R1','obligations':[{'property_id':'P1'},{'property_id':'missing'}]}]}
    rows=[{'property_id':'P1','status':'pass','proof_kind':'bounded','activation':{'status':'reached'}}]
    result=requirement_obligations(plan,rows)
    assert result[0]['status']=='inconclusive'
    assert result[0]['obligations'][0]['missing']==['unbounded proof missing']
    assert result[0]['obligations'][1]['missing']==['property missing']


@pytest.mark.parametrize('mode,expected', [('valid','pass'),('bad','inconclusive'),('conflict','inconclusive')])
def test_native_cell_core(tmp_path,mode,expected):
    import json
    import shutil
    from argparse import Namespace
    from rvw.common.proc import run_group
    from rvw.formal.cores import run
    if not all(shutil.which(t) for t in ('yosys','z3')):
        pytest.skip('Yosys/Z3 required')
    root=tmp_path/'run'; (root/'sby/model').mkdir(parents=True)
    rtl=tmp_path/'top.v'
    body={'valid':'assert(a || !a);','bad':'assert(a);','conflict':'assume(a); assume(!a); assert(a);'}[mode]
    rtl.write_text('module top(input a); always @* begin '+body+' end endmodule')
    proc=run_group(['yosys','-Q','-T','-p',f'read_verilog -formal {rtl}; prep -top top; write_rtlil {root}/sby/model/design.il'],capture=True,timeout=10)
    assert proc.returncode==0
    (root/'result.json').write_text(json.dumps({'schema':'rvw.formal/1','assertions':1,'depth':2}))
    out=tmp_path/'core'
    run(Namespace(result=str(root),cell_level=True,depth=2,property=None,smt2=None,mapping=None,out=str(out),solver='z3',timeout=15,db=None,json=False))
    result=json.loads((out/'result.json').read_text())
    assert result['status']==expected
    if mode=='conflict': assert result['bounded_model']['feasibility']=='unsat'
    assert result['cell_coverage']['status']==('bounded_core' if mode=='valid' else 'inconclusive')


def test_specification_replacement_preserves_design_equations():
    from rvw.formal.cell_model import vacuity_queries
    m=module()
    m['cells']['or']={'type':'$_OR_','connections':{'A':[2],'B':[3],'Y':[4]}}
    m['cells']['assert']['connections']['A']=[4]
    probes=vacuity_queries(m,2,None)
    assert len(probes)==1 and probes[0]['atom_bit']==2
    assert '(or false (not false))' in probes[0]['replacements'][0]
    assert '(or true (not true))' in probes[0]['replacements'][1]
