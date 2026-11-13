"""Full-word bus read capture must preserve instruction-level checks."""
import pytest
from rvw.cosim.platform import Platform

pytestmark = pytest.mark.fast


def platform():
    return Platform('declared', 32, 'rv32im', 0x80000000,
                    [(0x80000000, 4096)], [], aligned_mem=True,
                    memory_read_convention='full_word')


@pytest.mark.parametrize('funct3,size', [(0,1),(1,2),(2,4),(4,1),(5,2)])
def test_declared_read_lanes(funct3, size):
    p=platform()
    for offset in range(0,4,size):
        r=dict(insn=(offset<<20)|(1<<15)|(funct3<<12)|(3<<7)|3,
               rs1_rdata=0x80000000,trap=False,mem_addr=0x80000000,
               mem_rmask=15,mem_wmask=0,mem_rdata=0xaabbccdd,rd_wdata=0xdeadbeef)
        actual=p.normalize_record(r)
        assert actual['mem_rmask']==((1<<size)-1)<<offset
        assert actual['mem_rdata']==r['mem_rdata']
        assert actual['rd_wdata']==r['rd_wdata']
        assert r['mem_rmask']==15


@pytest.mark.parametrize('field,value', [('mem_addr',0x80000004),('mem_rmask',7),('mem_wmask',1),('insn',0x13)])
def test_bad_raw_read_is_refused(field, value):
    r=dict(insn=0x8183,rs1_rdata=0x80000000,trap=False,
           mem_addr=0x80000000,mem_rmask=15,mem_wmask=0,mem_rdata=0)
    r[field]=value
    with pytest.raises(ValueError): platform().normalize_record(r)


def test_default_read_and_store_strobes_stay_strict():
    p=platform();p.memory_read_convention='architectural'
    r=dict(mem_rmask=15)
    assert p.normalize_record(r) is r
    p.memory_read_convention='full_word'
    r=dict(mem_rmask=0,mem_wmask=3)
    assert p.normalize_record(r) is r
