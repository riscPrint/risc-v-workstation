from dataclasses import replace
import pytest
from rvw.ooo.core import Config,Instruction,simulate
from rvw.ooo.wrongpath import Work

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('frontend',[{},dict(decode_width=2,decode_entries=8,decode_latency=1,fetch_latency=1)])
def test_real_wrong_entries_squash_without_store_commit(frontend):
    c=Config(2,8,2,16,2,8,4,4,2,
        dict(alu=1,branch=10,jump=1,load=1,store=1),branch_penalty=3,frontend=frontend)
    ops=[Instruction('alu',dest=1,pc=0x100,next_pc=0x104),
         Instruction('branch',pc=0x104,next_pc=0x200),
         Instruction('load',(1,),2,pc=0x200,next_pc=0x204,address=0x1000,size=4)]
    wrong=[Instruction('alu',dest=1,pc=0x108,next_pc=0x10c),
           Instruction('load',dest=3,pc=0x10c,next_pc=0x110,address=0x2000,size=4),
           Instruction('store',(1,3),pc=0x110,next_pc=0x114,address=0x3000,size=4),
           Instruction('jump',pc=0x114,next_pc=0x108)]
    accesses=[]
    class Memory:
        def access(self,address,size,write,cycle):
            accesses.append((address,write,cycle));return 1
    w=Work(ops,{1:wrong})
    result=simulate(ops,c,backend='python',memory=Memory(),wrong_path=w)
    assert result['instret']==3
    assert result['events']['branches']==1
    assert result['events']['wrong_path_issued']>=3
    assert result['events']['wrong_path_squashed']==len(wrong)
    assert result['events']['issued']==3+result['events']['wrong_path_issued']
    assert result['events']['wrong_path_store_requests_suppressed']==1
    assert any(a==0x2000 for a,_,_ in accesses)
    assert not any(a==0x3000 and write for a,write,_ in accesses)
    assert [cycle for _,_,cycle in accesses]==sorted(cycle for _,_,cycle in accesses)
    assert result['max_occupancy']['rob_entries']<=c.rob_entries


def test_no_provider_preserves_default_engine():
    c=Config(1,2,1,4,1,2,1,1,1,dict(alu=1))
    ops=[Instruction('alu')]*3
    assert simulate(ops,c,backend='python')==simulate(ops,c,backend='python',wrong_path=None)
