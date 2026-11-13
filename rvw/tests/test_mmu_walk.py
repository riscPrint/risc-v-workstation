"""Independent walker tests. Native smoke covers only short Spike programs."""
import copy
import json
import shutil

import pytest

from rvw.regress import mmu
from rvw.regress.mmu_paging import MODES, page_tables
from rvw.regress.mmu_walk import walk, check, fault_matrix, validate_capture


def access(s):
    g = MODES[s['mode']]
    tables, _ = page_tables(s, mmu.ROOT, mmu.DATA, sum(mmu.FLAGS[f] for f in set(s['flags'])))
    memory = {mmu.ROOT + d * 4096 + i * g.width: p for d, table in enumerate(tables) for i, p in enumerate(table)}
    denied = [a for a in memory if a // 4096 == (mmu.ROOT // 4096 + g.levels - 1 - s['walk_deny_level'])] if 'walk_deny_level' in s else []
    return dict(mode=s['mode'], root=mmu.ROOT, va=0x40000000, access=s['access'], memory=memory, denied=denied)


@pytest.mark.parametrize('s', fault_matrix(list(MODES)), ids=lambda s: s['id'])
def test_fault_levels(s):
    mmu.validate(s)
    assert ('csrw mepc, t3' if s['access'] == 'fetch' else 'access_site:') in mmu.assembly(s)
    expected = walk(**access(s))
    assert expected['status'] == s['expect']
    fault_level = s.get('pte_fault_level', s.get('walk_deny_level'))
    assert expected['reads'][-1]['level'] == fault_level
    assert len(expected['reads']) == MODES[s['mode']].levels - fault_level


@pytest.mark.parametrize('mode', MODES)
def test_ordered_changes_and_mutations(mode):
    a = access(dict(mode=mode, level=0, access='load', flags='VRWAD'))
    b = copy.deepcopy(a)
    leaf = walk(**a)['reads'][-1]['address']
    b['memory'][leaf] += 1 << 10
    records = [dict(kind='mmu_walk', access_id=i, **{k: v for k, v in x.items() if k not in ('memory', 'denied')}, **walk(**x)) for i, x in enumerate((a, b))]
    for r in records:
        validate_capture(r)
    assert check(records, [a, b])['status'] == 'consistent'
    assert check([], [a])['status'] == 'inconclusive'
    assert check(records[:1], [a, b])['status'] == 'inconclusive'
    stale = copy.deepcopy(records)
    stale[1].update(reads=records[0]['reads'], pa=records[0]['pa'])
    assert check(stale, [a, b])['status'] == 'mismatch'
    for key, value in [('level', 0), ('address', 0), ('data', 0)]:
        bad = copy.deepcopy(records)
        bad[0]['reads'][0][key] = value
        assert check(bad, [a, b])['status'] == 'mismatch'
    assert check(records[::-1], [a, b])['status'] == 'mismatch'


def test_reference_does_not_infer_memory():
    with pytest.raises(ValueError, match='missing reference'):
        walk(mode='sv39', root=mmu.ROOT, va=0, access='load', memory={})


def test_spike_fault_levels(tmp_path):
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    desc = tmp_path / 'faults.json'
    desc.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=fault_matrix(list(MODES)))))
    mmu.build(desc, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', [(r['id'], r['stderr']) for r in result['scenarios'] if r['status'] != 'pass']


def test_c2_capture_and_identity(tmp_path):
    from rvw.regress.mmu_walk import check_c2, scenario_accesses
    from rvw.cosim.trace import HEX, INT, BOOL
    a = access(dict(mode='sv39', level=0, access='load', flags='VRWAD'))
    capture = dict(kind='mmu_walk', access_id=0, mode='sv39', root=a['root'], va=a['va'], access='load', **walk(**a))
    header = dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='fixture', config='test', elf='fixture', elf_sha256='e', rtl_sha256='r', source={}, seed=1)
    row = {**dict.fromkeys(HEX, '0x0'), **dict.fromkeys(INT, 0), **dict.fromkeys(BOOL, False), 'mode': 3, 'mmu_walks': [capture]}
    path = tmp_path / 'trace.jsonl'
    def save(end=True):
        path.write_text('\n'.join(json.dumps(r) for r in [header, row] + ([dict(event='end', cycle=1, status='pass')] if end else [])))
    save()
    assert check_c2(path, [a], header)['status'] == 'consistent'
    assert check_c2(path, [a], dict(header, seed=2))['status'] == 'inconclusive'
    save(False)
    assert check_c2(path, [a], header)['status'] == 'inconclusive'
    save()
    row['mmu_walks'][0]['reads'][0]['fault'] = 'false'
    save()
    with pytest.raises(ValueError, match='invalid PTE level or fault'):
        check_c2(path, [a])
    s = dict(mode='sv39', level=0, access='load', flags='VRWAD', remap=True)
    plans = scenario_accesses(s)
    assert walk(**plans[1])['pa'] == walk(**plans[0])['pa'] + 4096
    assert scenario_accesses(dict(s, root_switch=True)) == []


def test_unsupported_reference_is_not_a_mismatch():
    assert check([dict(kind='mmu_walk')], [])['status'] == 'inconclusive'
