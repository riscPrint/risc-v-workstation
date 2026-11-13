import json
import pytest
from rvw.perf.function_topdown import attribute, compare
from rvw.probes.events import Probe, Stream

pytestmark = pytest.mark.fast
KEYS = ('retiring','bad_speculation','backend_bound','frontend_bound')


def test_next_retirement_and_trailing_unknown():
    stream = Stream({}, [Probe(0,'custom','topdown_cycle',[(k,2) for k in KEYS])],
                    [(1,0,[0,0,0,2]),(2,0,[1,0,1,0]),(3,0,[0,2,0,0])], {})
    rows = attribute(stream, [{'cycle':2,'pc':'0x10'}], lambda pc: 'f' if pc==16 else None)
    assert rows['f'] == dict(zip(KEYS,[1,0,1,2]))
    assert rows['(unknown)']['bad_speculation'] == 2
    with pytest.raises(ValueError, match='totals are insufficient'):
        attribute(Stream({}, [], [], {}), [], lambda pc: None)


def test_compare_requires_same_workload(tmp_path):
    a = dict(schema='rvw.topdown/1', elf_sha256='a', cycles=10, slots=dict(zip(KEYS,[5,1,12,2])),
             functions={'f':dict(zip(KEYS,[5,1,12,2]))}, attribution='next retirement')
    b = {**a,'cycles':8,'slots':dict(zip(KEYS,[5,1,8,2])), 'functions':{'f':dict(zip(KEYS,[5,1,8,2]))}}
    p,q=tmp_path/'a.json',tmp_path/'b.json'
    p.write_text(json.dumps(a));q.write_text(json.dumps(b))
    r=compare(p,q)
    assert r['cycles_delta']==-2 and r['functions']['f']['backend_bound']==-4
    b['elf_sha256']='b';q.write_text(json.dumps(b))
    with pytest.raises(ValueError,match='same ELF'):
        compare(p,q)


def test_mixed_function_retirement_is_exact():
    stream = Stream({}, [Probe(0,'custom','topdown_cycle',[(k,2) for k in KEYS])],
                    [(2,0,[2,0,0,0])], {})
    records=[{'cycle':2,'pc':'0x10'},{'cycle':2,'pc':'0x20'}]
    rows=attribute(stream,records,lambda pc:'a' if pc==16 else 'b')
    assert rows['a']['retiring']==rows['b']['retiring']==1
    stream.rows[0]=(2,0,[1,0,1,0])
    with pytest.raises(ValueError,match='at this cycle'):
        attribute(stream,records,lambda pc:'a')
