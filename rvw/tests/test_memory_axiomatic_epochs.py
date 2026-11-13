import json
import pytest
from rvw.cosim.trace import HEX, INT, BOOL
from rvw.memory.axiomatic import check

pytestmark = pytest.mark.fast


def execution(tmp_path, middle):
    def record(order, epoch, insn, model=None, **fields):
        r={k:'0x0' for k in HEX} | {k:0 for k in INT} | {k:False for k in BOOL}
        r.update(hart=0,epoch=epoch,order=str(order),mode=3,insn=hex(insn))
        if model is not None:
            r['memory_model']=dict(id=model, hart=0, order=order, kind='R', address=0, size=8,
                                   read=0, addr=[], data=[], ctrl=[])
        return r | fields
    rows=[dict(event='reset',hart=h,epoch=0) for h in (0,1)]
    last_epoch=0
    if middle=='cross-reset-sc':
        lr=record(0,0,(2<<27)|(3<<12)|47,'lr',mem_rmask=255)
        lr['memory_model']['kind']='LR'
        rows += [lr,dict(event='reset',hart=0,epoch=1),record(0,1,0x100093,rd=1,rd_wdata='0x1')]
        sc=record(1,1,(3<<27)|(1<<20)|(3<<12)|47,mem_wmask=255,mem_wdata='0x1',rs2=1,rs2_rdata='0x1')
        sc['memory_model']=dict(id='sc',hart=0,order=1,kind='SC',address=0,size=8,write=1,rmw='lr',addr=[],data=[],ctrl=[])
        rows.append(sc); last_epoch=1
    else:
        if middle=='maintenance':
            rows.append(dict(event='external',id='maintenance',action='maintenance',source='cache',address='0x0',data='0x0',mask='0x0'))
        if middle=='trap':
            rows.append(dict(event='trap',hart=0,epoch=0,cause='0x2',tval='0x0',intr=False))
        rows.append(record(0,0,0x3003,'r',mem_rmask=255))
    rows += [dict(event='hart_end',hart=0,epoch=last_epoch,status='pass'),dict(event='hart_end',hart=1,epoch=0,status='pass')]
    header=dict(schema='rvw.rvfi/2',xlen=64,isa='rv64ia',core='fixture',config='two',elf='fixture',harts=[0,1],
                memory_dependencies='complete',memory_addresses='physical')
    trace=tmp_path/'trace.jsonl'
    trace.write_text(json.dumps(header)+'\n'+''.join(json.dumps(r | dict(cycle=i,capture_seq=str(i)))+'\n' for i,r in enumerate(rows)))
    initial=tmp_path/'initial.json'
    initial.write_text(json.dumps(dict(schema='rvw.axiomatic-initial/1',locations=[dict(address='0x0',size=8,value='0x0')])))
    return trace,initial


@pytest.mark.parametrize('model',['rvwmo','ztso'])
@pytest.mark.parametrize('middle,reason',[('cross-reset-sc','reset'),('maintenance','maintenance'),('trap','trap')])
def test_unmodelled_capture_domains_cannot_return_allowed(tmp_path, middle, reason, model):
    report=check(*execution(tmp_path,middle),model=model)
    assert report['status']=='inconclusive', report
    assert reason in report['reason']


@pytest.mark.parametrize('model',['rvwmo','ztso'])
def test_initial_reset_and_ordinary_memory_remain_supported(tmp_path,model):
    assert check(*execution(tmp_path,'ordinary'),model=model)['status']=='allowed'
