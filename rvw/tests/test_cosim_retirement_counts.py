"""A trapping C2 record is compared but does not increment C1 instret."""
import json
from types import SimpleNamespace

import pytest
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from rvw.cosim.extensions import complete_comparison as complete

pytestmark = pytest.mark.fast


def test_trapping_record_is_not_a_retirement(tmp_path):
    platform = Platform.load('boom')
    def row(order, pc, insn, trap=False, intr=False):
        return dict(order=order,cycle=order+1,pc=hex(pc),pc_next=hex(0x80000100 if trap else pc+4),
                    insn=hex(insn),mode=3,trap=trap,intr=intr,halt=False,mem_fault=False,
                    rs1=0,rs2=0,rd=0,mem_rmask=0,mem_wmask=0,
                    **{k:'0x0' for k in ('rs1_rdata','rs2_rdata','rd_wdata','mem_addr','mem_rdata','mem_wdata')})
    rows = [row(0,0x80000000,0x73,True),row(1,0x80000100,0x13,intr=True)]
    class Model:
        def __init__(self):
            self.effects = iter(rows)
        def step(self, **kwargs):
            r = next(self.effects)
            return {**{k:int(v,16) if isinstance(v,str) else v for k,v in r.items()},
                    'cause':11 if r['trap'] else 0,'tval':0,'regs':[0]*32,'disasm':'fixture'}
    path = tmp_path/'trace.jsonl'
    header = dict(schema='rvw.rvfi/1',xlen=64,isa=platform.isa,core='fixture',config='test',elf='fixture')
    path.write_text('\n'.join(json.dumps(r) for r in [header,*rows,
                    dict(event='end',cycle=3,status='pass',records=2)])+'\n')
    report = check(path,Model(),platform,sync=())
    assert report['status'] == 'match', report
    assert report['instructions'] == 2
    assert report['retirements'] == 1
    assert complete(report,SimpleNamespace(instret=1))
    assert not complete(report,SimpleNamespace(instret=2))


@pytest.mark.parametrize('retirements,accepted',[(2,True),(1,False),(3,False),(-1,False),(True,False),('2',False)])
def test_completion_checks_the_nontrapping_count(retirements,accepted):
    report = dict(status='match',synchronized=0,trace_complete=True,end_status='pass',
                  instructions=3,retirements=retirements)
    assert complete(report,SimpleNamespace(instret=2)) is accepted


def test_legacy_nontrapping_comparison_remains_supported():
    report = dict(status='match',synchronized=0,trace_complete=True,end_status='pass',instructions=2)
    assert complete(report,SimpleNamespace(instret=2))
    assert not complete(report,SimpleNamespace(instret=1))
