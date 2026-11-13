"""Independent architectural effects and tagged bus observations."""
import pytest
from rvw.soc.pairing import pair_rows


def fixtures():
    retires=[dict(order=0,cycle=5,mem_addr='0x1000',mem_rmask=15,mem_wmask=0,
                  mem_rdata='0x44332211',mem_wdata='0x0',mem_fault=False)]
    events=[dict(event='request',cycle=1,tag='load-0',write=False,address='0x1000',mask=15,data=0),
            dict(event='response',cycle=3,tag='load-0',data='0x44332211',error=False),
            dict(event='retire_link',cycle=5,order=0,requests=['load-0'])]
    return retires,events


def test_independently_observed_tag_pair():
    retires,events=fixtures()
    result=pair_rows(retires,events,4)
    assert result['status']=='inconclusive' and not result['gaps']
    assert len(result['pairs'])==1
    assert all(row['status']=='consistent' for row in result['pairs'][0]['checks'])


@pytest.mark.parametrize('field,value',[('data','0x44332212'),('error',True),('cycle',6)])
def test_wrong_response_is_not_a_match(field,value):
    retires,events=fixtures();events[1][field]=value
    events.sort(key=lambda e:e['cycle'])
    assert pair_rows(retires,events,4)['status']=='mismatch'


def test_missing_tag_is_incomplete_and_duplicates_refused():
    retires,events=fixtures()
    result=pair_rows(retires,events[:-1],4)
    assert not result['pairs'] and result['gaps']
    with pytest.raises(ValueError,match='multiple'):
        pair_rows(retires+[dict(retires[0],order=1,cycle=6)],events+[dict(events[-1],order=1,cycle=6)],4)


def test_split_beats_pair_by_tags():
    retires,events=fixtures()
    events=[dict(events[0],mask=3),dict(events[0],tag='load-1',address='0x1002',mask=3),
            dict(events[1],data='0x2211'),dict(events[1],tag='load-1',data='0x4433'),
            dict(events[2],requests=['load-0','load-1'])]
    assert pair_rows(retires,events,2)['status']=='inconclusive'
    events[1]['address']='0x1000'
    assert pair_rows(retires,events,2)['status']=='mismatch'


def test_missing_response_is_not_a_mismatch():
    retires,events=fixtures()
    assert pair_rows(retires,[events[0],events[2]],4)['status']=='inconclusive'


def test_posted_store_response_is_a_gap():
    retires,events=fixtures()
    retires[0].update(mem_rmask=0,mem_wmask=15,mem_wdata='0x44332211')
    events[0].update(write=True,data='0x44332211')
    events[1]['cycle']=7
    events.sort(key=lambda e:e['cycle'])
    result=pair_rows(retires,events,4)
    assert result['status']=='inconclusive' and result['gaps']


def test_captured_identity_and_independent_trace(tmp_path):
    import hashlib,json
    from rvw.cosim.trace import record
    from rvw.soc.pairing import check
    header=dict(schema='rvw.rvfi/1',xlen=32,isa='rv32i',core='unit',config='unit',elf='unit.elf')
    effect=dict(pc=0x1000,pc_next=0x1004,insn=0x0000a183,mode=3,rd=3,rd_wdata=0x44332211,
                mem_addr=0x1000,mem_rmask=15,mem_wmask=0,mem_rdata=0x44332211,mem_wdata=0,
                trap=False,mem_fault=False,before=[0,0x1000]+[0]*30)
    trace=tmp_path/'trace.jsonl'
    trace.write_text('\n'.join(json.dumps(row) for row in [header,record(effect,0,cycle=5,xlen=32),dict(event='end',cycle=6,status='pass')])+'\n')
    run=dict(source={'rev':'fixture'},rtl_sha256='rtl-fixture',elf_sha256='elf-fixture',seed=1,
             details={'simulation_session':{'run_id':'run-1'}})
    result=tmp_path/'result.json';result.write_text(json.dumps(run))
    identity=dict(schema='rvw.soc-events/1',observation='rtl_request_response_retire_tags',data_bytes=4,
                  trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),run_id='run-1',
                  **{key:run[key] for key in ('source','rtl_sha256','elf_sha256','seed')})
    capture=tmp_path/'bus.jsonl'
    _,events=fixtures()
    def save():
        capture.write_text('\n'.join(json.dumps(row) for row in [identity,*events])+'\n')
    save()
    assert check(capture,trace,result)['status']=='inconclusive'
    identity['run_id']='other';save()
    with pytest.raises(ValueError,match='session'):
        check(capture,trace,result)
    identity['run_id']='run-1';identity['trace_sha256']='stale';save()
    with pytest.raises(ValueError,match='trace hash'):
        check(capture,trace,result)


def test_command_and_mcp_registration():
    import argparse
    from rvw.soc.pairing import register,mcp_tools
    parser=argparse.ArgumentParser();register(parser.add_subparsers())
    args=parser.parse_args(['pair','--capture','bus','--trace','trace','--result','result','--out','out'])
    assert args.capture=='bus' and args.trace=='trace'
    assert mcp_tools()[0].name=='soc_pair'
