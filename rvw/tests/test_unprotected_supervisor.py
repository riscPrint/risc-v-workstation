"""No-PMP bootstrap and native read-bus walk observations."""
from pathlib import Path
import hashlib
import json
from types import SimpleNamespace
import pytest
from rvw.regress import mmu
from rvw.regress.mmu_observe import check_walk
from rvw.privilege import programs, scheduled

pytestmark = pytest.mark.fast


def scenario(**extra):
    return dict(id='sv39-load', mode='sv39', level=0, flags='VRWAD', access='load',
                expect='success', bins=['load'], **extra)


def events():
    rows = []
    for address, data in [(mmu.ROOT+8, ((mmu.ROOT+4096)>>12)<<10|1),
                          (mmu.ROOT+4096, ((mmu.ROOT+8192)>>12)<<10|1),
                          (mmu.ROOT+8192, (mmu.DATA>>12)<<10|0xc7)]:
        rows += [dict(cycle=len(rows),kind='walk_request',address=address,command=0),
                 dict(cycle=len(rows)+1,kind='walk_response',address=address,data=data,fault=False)]
    rows.append(dict(cycle=10,kind='memory_read',address=mmu.DATA,size_log2=6))
    return rows


def test_base_translation_no_pmp_retains_access_and_checks():
    text = mmu.assembly(scenario(pmp_regions=0))
    assert 'pmpaddr' not in text and 'pmpcfg' not in text
    assert 'csrw satp, t0' in text and 'ld a0, 0(t3)' in text
    assert 'fail:' in text and '.section .tables' in text
    assert 'csrw pmpaddr0, t0' in mmu.assembly(scenario())


def test_no_pmp_cannot_silently_remove_walk_denial():
    with pytest.raises(ValueError, match='walk denial requires PMP'):
        mmu.assembly(scenario(pmp_regions=0,walk_deny=True))


def test_privilege_and_interrupt_body_counts_unchanged_without_pmp():
    rows = programs.controls(dict(pmp=dict(entries=0)))
    assert len(rows) == 30
    assert all('pmpaddr' not in r['assembly'] and 'access_site:' in r['assembly'] for r in rows)
    assert all('pmpaddr0' in r['assembly'] for r in programs.controls({}))
    rows = scheduled.programs(dict(pmp=dict(entries=0),wake=dict(assert_cycle=1000,clear_cycle=20000)))
    assert len(rows) == 6 and all('pmpaddr' not in r['assembly'] for r in rows)
    assert all('irq_schedule' in r['options'] for r in rows)


def test_native_read_bus_can_witness_target_without_tilelink_opcode():
    assert check_walk(scenario(), events())['status'] == 'consistent'
    assert check_walk(scenario(), events()[:-1])['status'] == 'inconclusive'


def test_faulted_pte_response_cannot_count_as_a_valid_read():
    rows = events(); rows[5]['fault'] = True
    assert check_walk(scenario(), rows)['status'] == 'mismatch'


@pytest.mark.parametrize('corrupt', [False, True])
def test_observation_binding_allows_runner_enrichment_not_changed_source(tmp_path,monkeypatch,corrupt):
    import rvw.results
    built = tmp_path/'built';built.mkdir();run=tmp_path/'run';run.mkdir()
    (built/'test.elf').write_bytes(b'fixture')
    sha=hashlib.sha256(b'fixture').hexdigest()
    (built/'manifest.json').write_text(json.dumps(dict(scenarios=[dict(scenario(),elf='test.elf',elf_sha256=sha)])))
    identity=dict(core='fixture',config='rv64',elf_sha256=sha,rtl_sha256='a'*64,seed=1,source=dict(core_rev='a'))
    raw=dict(identity,source=dict(core_rev='a',runner_extra=True),details=dict(mmu_observations='mmu.jsonl'))
    (run/'result.json').write_text(json.dumps(raw))
    if corrupt:identity['source']=dict(core_rev='b')
    rows=[dict(schema='rvw.mmu-observations/1',elf_sha256=sha,identity=identity),*events()]
    (run/'mmu.jsonl').write_text('\n'.join(map(json.dumps,rows))+'\n')
    monkeypatch.setattr(mmu,'run_paths_under',lambda _: [run])
    monkeypatch.setattr(rvw.results,'load_run',lambda _:SimpleNamespace(path=run,elf_sha256=sha,artifacts={}))
    report=mmu.report(built,run)
    assert report['scenarios'][0]['observations']['walk_check']['status'] == ('inconclusive' if corrupt else 'consistent')


def test_seeded_transitions_use_the_same_no_pmp_bootstrap():
    from rvw.privilege.random_transitions import programs as random_programs
    config = dict(isa='rv64ima_zicsr', spec_version='privileged-20260120',
                  random_transitions=dict(seeds=[1], steps=4), pmp=dict(entries=0))
    rows = random_programs(config)
    assert len(rows) == 1 and len(rows[0]['transition_plan']) == 4
    assert 'pmpaddr' not in rows[0]['assembly']
    assert 'csrw mepc' in rows[0]['assembly'] and 'csrr t0, mcause' in rows[0]['assembly']
    config.pop('pmp')
    assert 'pmpaddr0' in random_programs(config)[0]['assembly']


def test_fetch_walks_are_outside_the_data_walk_checker_scope():
    sample = scenario(); sample['access'] = 'fetch'
    # An OoO instruction stream can walk for the target and for wrong-path PCs.
    # The bounded data-walk checker cannot classify those extra requests.
    rows = events() + [dict(cycle=11, kind='walk_request', address=mmu.ROOT+16, command=0)]
    assert check_walk(sample, rows)['status'] == 'inconclusive'


def test_random_transitions_respect_declared_warl_delegation():
    from rvw.privilege.random_transitions import programs as random_programs
    config = dict(isa='rv64ima_zicsr', spec_version='privileged-20260120',
                  random_transitions=dict(seeds=[20260120], steps=1), pmp=dict(entries=0))
    default = random_programs(config)[0]
    assert default['transition_plan'][0]['delegated']
    config['random_transitions']['delegatable_causes'] = [3]
    selected = random_programs(config)[0]
    assert selected['transition_plan'][0] == dict(default['transition_plan'][0], delegated=False)
    assert 'li t1, 2' in selected['assembly'] and 'csrr t0, mcause' in selected['assembly']
    config['random_transitions']['delegatable_causes'] = [64]
    with pytest.raises(ValueError, match='delegatable_causes'):
        random_programs(config)
