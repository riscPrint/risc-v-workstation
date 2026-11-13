"""Fault tests for the sampled-run transfer equality gate."""
import copy
import json
import pytest
from rvw.cosim.trace import HEX, INT, BOOL
from rvw.sample.flow import compare

pytestmark=pytest.mark.fast


def fixture(tmp_path):
    header=dict(schema='rvw.rvfi/1',xlen=32,isa='rv32im',core='fixture',config='fixture',elf='fixture')
    rows=[]
    for i in range(4):
        r={k:'0x0' for k in HEX}
        r.update({k:0 for k in INT});r.update({k:False for k in BOOL})
        r.update(order=i,cycle=10+3*i,mode=3,pc=hex(0x100+4*i),pc_next=hex(0x104+4*i),
                 insn='0x12083',rs1=2,rs1_rdata='0x1000',rd=1,rd_wdata='0x123',mem_rmask=15,mem_rdata='0x123',mem_addr='0x1000')
        rows.append(r)
    expected=[{k:int(v,0) if k in HEX else v for k,v in r.items()} for r in rows]
    def save(rows=rows,end=True,status='pass'):
        path=tmp_path/'trace.jsonl'
        path.write_text('\n'.join(json.dumps(r) for r in [header,*rows]+([dict(event='end',cycle=20,status=status)] if end else []))+'\n')
        return path
    return rows,expected,save


@pytest.mark.parametrize('field,value',[('pc','0x20'),('pc_next','0x20'),('insn','0x33'),
    ('rd_wdata','0x8'),('mem_rdata','0x124'),('mem_addr','0x2000'),('mem_rmask',7)])
def test_measured_mismatch_excludes(field,value,tmp_path):
    rows,expected,save=fixture(tmp_path)
    rows[-1][field]=value
    with pytest.raises(ValueError,match='mismatch'):
        compare(save(),expected,1,3)


def test_complete_trace_matches(tmp_path):
    rows,expected,save=fixture(tmp_path)
    r=compare(save(),expected,1,3)
    assert r['status']=='matched' and r['ipc']==pytest.approx(1/3)


@pytest.mark.parametrize('failure',['truncated','no_end','failed_end','trap','warmup_mismatch'])
def test_incomplete_or_bad_transfer_rejected(tmp_path,failure):
    rows,expected,save=fixture(tmp_path)
    if failure=='truncated': rows.pop()
    if failure=='trap': rows[-1]['trap']=True
    if failure=='warmup_mismatch': rows[0]['rd_wdata']='0x8'
    path=save(end=failure!='no_end',status='fail' if failure=='failed_end' else 'pass')
    with pytest.raises(ValueError): compare(path,expected,1,3)


def test_byte_load_ignores_inactive_bus_lanes(tmp_path):
    rows,expected,save=fixture(tmp_path)
    for r,e in zip(rows,expected):
        r.update(insn='0x14083',rd_wdata='0x23',mem_rmask=1,mem_rdata='0xbeef0023')
        e.update(insn=0x14083,rd_wdata=0x23,mem_rmask=1,mem_rdata=0x23)
    assert compare(save(),expected,1,3)['status']=='matched'
    rows[-1]['mem_rdata']='0xbeef0024'
    with pytest.raises(ValueError,match='mismatch'):
        compare(save(),expected,1,3)
