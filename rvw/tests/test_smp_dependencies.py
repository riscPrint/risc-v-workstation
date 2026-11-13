import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
path = Path(__file__).resolve().parents[2]/'examples/smp/rvw/scalar_dependencies.py'
spec = importlib.util.spec_from_file_location('smp_dependencies',path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Dependencies = module.Dependencies


def record(insn, order=0, address=0x81000000, rmask=0, wmask=0):
    return dict(insn=insn, order=order, hart=0, epoch=0, trap=False, mem_fault=False,
                mode=3, mem_addr=address, mem_rmask=rmask, mem_wmask=wmask,
                mem_rdata=0, mem_wdata=1)


def load(rd, rs1=1):
    return 0x03 | rd<<7 | 3<<12 | rs1<<15


def store(rs2,rs1=1):
    return 0x23 | 3<<12 | rs1<<15 | rs2<<20


def test_address_data_and_load_no_carry():
    d=Dependencies()
    first=d.observe(record(load(5),rmask=255))
    d.observe(record(0x13 | 6<<7 | 5<<15 | 1<<20,1))
    w=d.observe(record(store(6),2,wmask=255))
    assert w['data']==[first['id']] and w['addr']==[]
    second=d.observe(record(load(7,5),3,rmask=255))
    assert second['addr']==[first['id']]
    w=d.observe(record(store(7),4,wmask=255))
    assert w['data']==[second['id']]


def test_control_and_constant_overwrite_and_zero_register():
    d=Dependencies()
    event=d.observe(record(load(5),rmask=255))
    d.observe(record(0x63 | 1<<12 | 5<<15,1)) # BNE x5,x0
    d.observe(record(0x37 | 5<<7,2))  # LUI overwrites x5
    w=d.observe(record(store(5),3,wmask=255))
    assert w['data']==[] and w['ctrl']==[event['id']]
    d.observe(record(load(0),4,rmask=255))
    assert not d.regs[0]


def test_pairing_is_consumed_by_failed_sc():
    d=Dependencies()
    lr=2<<27 | 1<<15 | 3<<12 | 5<<7 | 0x2f
    sc=3<<27 | 6<<20 | 1<<15 | 3<<12 | 7<<7 | 0x2f
    e=d.observe(record(lr,rmask=255))
    paired=d.observe(record(sc,1,wmask=255))
    assert paired['rmw']==e['id']
    d.observe(record(lr,2,rmask=255))
    before=set(d.regs[7])
    assert d.observe(record(sc,3)) is None
    assert d.regs[7] == before
    with pytest.raises(ValueError,match='no observed matching LR'):
        d.observe(record(sc,4,wmask=255))


@pytest.mark.parametrize('changes', [dict(insn=0x00000073), dict(mode=1),
                                    dict(trap=True), dict(mem_fault=True),
                                    dict(mem_addr=0x2000000)])
def test_unsupported_evidence_refuses_completeness(changes):
    r=record(load(5),rmask=255)
    r.update(changes)
    with pytest.raises(ValueError):
        Dependencies().observe(r)


@pytest.mark.parametrize('insn',[0x40001013, 0x0200103b, 2<<27 | 1<<20 | 3<<12 | 0x2f])
def test_reserved_encodings_refuse_dependencies(insn):
    with pytest.raises(ValueError):
        Dependencies().observe(record(insn,rmask=255))
