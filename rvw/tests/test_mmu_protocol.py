import copy
import pytest
from rvw.regress.mmu_protocol import check


def run(events, **kw):
    return check([dict(e, cycle=i) for i, e in enumerate(events)], required_harts=[0, 1], **kw)


def fill(hart=0):
    return dict(kind='tlb_fill', hart=hart, entry='a', va=0x10000, pa=0x20000, size=65536, asid=7, pte_address=0x1000, pte=0xc7)


def test_napot_range_and_stale_hit():
    start = [dict(kind='pte_write', address=0x1000, data=0xc7), fill()]
    hit = dict(kind='tlb_hit', hart=0, entry='a', va=0x1f000, pa=0x2f000, asid=7)
    assert run(start + [hit])['status'] == 'consistent'
    invalidate = dict(kind='tlb_invalidate', hart=0, va=0x1a000, asid=7)
    assert run(start + [invalidate, hit])['status'] == 'mismatch'
    assert run(start + [dict(invalidate, asid=8), hit])['status'] == 'consistent'
    assert run(start + [dict(kind='pte_write', address=0x1000, data=0x1c7), fill()])['status'] == 'mismatch'


def test_global_and_over_invalidation():
    start = [dict(kind='pte_write', address=0x1000, data=0xc7), dict(fill(), **{'global': True})]
    hit = dict(kind='tlb_hit', hart=0, entry='a', va=0x10000, pa=0x20000, asid=8)
    invalidate = dict(kind='tlb_invalidate', hart=0, va=None, asid=7)
    assert run(start + [invalidate, hit])['status'] == 'consistent'
    assert run(start + [dict(invalidate, asid=None), hit])['status'] == 'mismatch'


def test_atomic_ad_preserves_concurrent_software_bits():
    events = [dict(kind='pte_write', address=0x1000, data=7), dict(kind='pte_write', address=0x1000, data=0x107),
              dict(kind='ad_atomic', address=0x1000, old=0x107, new=0x1c7, set_bits=192)]
    assert run(events)['status'] == 'consistent'
    events[-1].update(old=7, new=0xc7)
    assert run(events)['status'] == 'mismatch'


def test_shootdown_completion_and_scope():
    events = [dict(kind='shootdown_request', request='r', targets=[1], va=0x10000, asid=7),
              dict(kind='tlb_invalidate', hart=1, va=0x10000, asid=7),
              dict(kind='shootdown_ack', request='r', hart=1), dict(kind='shootdown_complete', request='r')]
    assert run(events)['status'] == 'consistent'
    bad = copy.deepcopy(events)
    bad[1]['va'] += 4096
    assert run(bad)['status'] == 'mismatch'
    assert run([events[0], events[-1]])['status'] == 'mismatch'


def test_memory_policy_required():
    events = [dict(kind='memory_type', pbmt=2, memory_type='io')]
    assert run(events)['status'] == 'inconclusive'
    assert run(events, pbmt_types={'2': 'io'})['status'] == 'consistent'
    assert run(events, pbmt_types={'2': 'nc'})['status'] == 'mismatch'
    assert run([])['status'] == 'inconclusive'


def test_atomic_and_ipi_spike(tmp_path):
    import json
    import shutil
    from rvw.regress import mmu
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    cases = []
    for mode in ('sv39', 'sv48', 'sv57'):
        cases.append(dict(id=f'{mode}-atomic-ad', mode=mode, atomic_ad=True, level=0, flags='VRW', access='store', expect='success', bins=[f'{mode}.atomic-ad']))
        cases.append(dict(id=f'{mode}-ipi', mode=mode, shootdown=True, ipi=dict(msip=0x2000000, stride=4), level=0, flags='VRWAD', access='load', expect='success', bins=[f'{mode}.ipi']))
    desc = tmp_path / 'programs.json'
    desc.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=cases)))
    mmu.build(desc, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', [(r['id'], r['stderr']) for r in result['scenarios'] if r['status'] != 'pass']


def test_protocol_events_do_not_break_raw_walker():
    from rvw.regress.mmu_observe import check_walk
    s = dict(mode='sv39', level=0, flags='VRWAD', access='load', expect='success')
    assert check_walk(s, [dict(kind='tlb_invalidate', cycle=0, hart=0, va=None, asid=None)])['status'] == 'inconclusive'
