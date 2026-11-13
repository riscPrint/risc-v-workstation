import importlib
import json
from types import SimpleNamespace
import pytest
pytestmark = pytest.mark.fast

@pytest.mark.parametrize('isa,schema', [('rv32imafc','rvw.rvfi/2'),('rv64imafdc','rvw.rvfi/2'),('rv64imac','rvw.rvfi/1')])
def test_generate_exports_scalar_fp_state(monkeypatch,tmp_path,isa,schema):
    module=importlib.import_module('rvw.cosim.generate')
    effect=dict(insn=0x13,pc=0,pc_next=4,rd=0,rd_wdata=0,before=[0]*32,mode=3,
                mem_addr=0,mem_rdata=0,mem_wdata=0,mem_rmask=0,mem_wmask=0,
                trap=False,intr=False,halted=True,mem_fault=False,
                fd_valid=True,fd=0,fd_wdata=0xffffffff7fc00000,fflags=16,fcsr=112)
    class Model:
        def __init__(self,*a,**kw): self.elf=SimpleNamespace(symbols={})
        def step(self): return effect
        def close(self): pass
    monkeypatch.setattr(module,'Spike',Model)
    out=tmp_path/'reference.jsonl'
    assert module.generate('program.elf',out,SimpleNamespace(isa=isa,xlen=int(isa[2:4]),name='test'),shim='unused')['termination']=='halt'
    header,row,_=map(json.loads,out.read_text().splitlines())
    assert header['schema']==schema
    if schema.endswith('/2'):
        assert header['capabilities']==['state']
        assert row['fd_valid'] and row['fd']==0
        assert row['fd_wdata']=='0xffffffff7fc00000'
        assert row['fflags']=='0x10' and row['fcsr']=='0x70'
    else:
        assert 'fd_wdata' not in row
