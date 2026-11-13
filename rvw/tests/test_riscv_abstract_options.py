import hashlib
import pytest
from rvw.formal import riscv_abstract as abstract

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('pipeline,memory',[(True,False),(False,True),(True,True)])
def test_isolate_each_reduction(tmp_path,monkeypatch,pipeline,memory):
    from rvw.formal import riscv_proof,portfolio,lazy_ram
    text='module Core(input clk,reset,a,b); always @(posedge clk) assert(a==b); endmodule'
    def capture(cfg,out):
        out.mkdir()
        (out/'check.sv').write_text(text)
        return dict(formal_inputs={},jobs=[dict(id='insn_add_ch0',top='Core',mode='prove',depth=5,
            sources=[dict(path='check.sv',sha256=hashlib.sha256(text.encode()).hexdigest())])])
    monkeypatch.setattr(riscv_proof,'capture',capture)
    calls=[]
    def ram(plan,root,out,**kwargs):
        calls.append('memory')
        source=(root/plan['sources'][0]['path']).read_text()
        assert ('assume(' in source)==pipeline
        return dict(status='inconclusive',conditional_native_proof=False,rounds=[])
    def race(plan,root,out,**kwargs):
        calls.append('pipeline')
        assert 'assume(' in (root/plan['sources'][0]['path']).read_text()
        return dict(status='inconclusive',rows=[dict(status='pass')])
    monkeypatch.setattr(lazy_ram,'run',ram)
    monkeypatch.setattr(portfolio,'race',race)
    monkeypatch.setattr(abstract,'cover',lambda *a:dict(status='reached'))
    plan=dict(schema='rvw.riscv-abstraction/1',module='Core',clock='clk',reset='reset',
              in_flight=['a','b'],memory='mem',pipeline_restriction=pipeline,ram_abstraction=memory)
    result=abstract.run(dict(depth=5,solver='yices'),plan,tmp_path/'out',timeout=2,budget=4)
    assert calls==['memory' if memory else 'pipeline']
    assert result['pipeline_restriction']==pipeline and result['ram_abstraction']==memory
    assert (result['restriction'] is not None)==pipeline
    assert result['status']=='inconclusive'
    assert result['rows'][0]['conditional_native_proof']==(not memory)


@pytest.mark.parametrize('pipeline,memory',[(False,False),('false',True),(True,1)])
def test_reject_ambiguous_reduction_options(tmp_path,pipeline,memory):
    with pytest.raises(ValueError,match='booleans'):
        abstract.run({},dict(schema='rvw.riscv-abstraction/1',pipeline_restriction=pipeline,
                             ram_abstraction=memory),tmp_path/'out')
    assert not (tmp_path/'out').exists()
