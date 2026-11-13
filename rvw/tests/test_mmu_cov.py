import json

from rvw.regress.mmu_cov import groups
from rvw.cov.functional import functional


import pytest

pytestmark = pytest.mark.fast


def test_capture_groups_and_hart_windows(tmp_path):
    plan = groups()
    plan['groups'].append(dict(name='dependency_fixture', fields=['back_to_back'], when=dict(event='retire')))
    config = tmp_path / 'groups.json'
    config.write_text(json.dumps(plan))
    walk = dict(kind='mmu_walk', access_id=0, mode='sv39', access='load', root=0x80010000, va=0x40000000, pa=0x80200000, status='success',
                reads=[dict(level=0, address=0x80012000, data=0xc7, fault=False)])
    def row(hart, insn, rd, **kw):
        return dict(hart=hart, epoch=0, order='0', cycle=hart+1, mode=3, insn=hex(insn), rd=rd,
                    pc='0x80000000', mem_rmask=0, mem_wmask=0, **kw)
    rows = [dict(schema='rvw.rvfi/2', xlen=64, isa='rv64i', core='fixture', config='test', elf='fixture', harts=[0,1]),
            dict(event='reset', cycle=0, hart=0, epoch=0), dict(event='reset', cycle=0, hart=1, epoch=0),
            row(0, 0x00100293, 5, mmu_walks=[walk], mmu_protocol=[dict(kind='tlb_fill', hart=0)],
                csr_state={'0x30a':'0x200000000'}, hypervisor=dict(csrs={'0x280':'0x8000000000000000','0x680':'0x9000000000000000'},
                                                                       translations=[dict(access='load')])),
            row(1, 0x00128313, 6, iommu=[dict(device=7, process=2, result='fault', stage='second', access='store', queue='fault', operation='enqueue')]),
            dict(event='end', cycle=3, status='pass')]
    trace = tmp_path / 'trace.jsonl'
    trace.write_text('\n'.join(json.dumps(r) for r in rows))
    report = functional([trace], config)
    result = report['unqualified']
    assert result['vm_mode_access_result'][0]['bin'] == ['sv39','load','success']
    assert result['vm_pointer_control'][0]['bin'] == ['menvcfg',2,'M']
    assert result['vm_two_stage'][0]['bin'] == [8,9,'load']
    assert result['iommu_stage_access'][0]['bin'] == ['second','store','fault']
    assert result['dependency_fixture'] == [dict(bin=[False],count=2)]


def test_no_capture_no_hits(tmp_path):
    from rvw.regress.mmu_cov import observations
    assert observations({}) == []
