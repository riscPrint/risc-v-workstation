import copy
import pytest
from rvw.regress.mmu_hypervisor import matrix
from rvw.regress.mmu_nested import scenario_accesses, translate, check


@pytest.mark.parametrize('s', [s for s in matrix() if 'ad_expect' not in s and not s.get('guest_op', '').startswith('vs-')], ids=lambda s:s['id'])
def test_generated_memory_and_mutations(s):
    accesses = scenario_accesses(s)
    assert accesses
    records = [dict(access_id=i, complete=True, **{k:v for k,v in a.items() if k != 'memory'}, result=translate(**a)) for i,a in enumerate(accesses)]
    assert check(records, accesses)['status'] == 'consistent'
    result = records[0]['result']
    assert result['status'] == ('success' if s['expect'] == 'success' else 'guest-page-fault' if s.get('guest_fault') else 'page-fault')
    incomplete = copy.deepcopy(records)
    incomplete[0]['complete'] = False
    assert check(incomplete, accesses)['status'] == 'inconclusive'
    assert check([], accesses)['status'] == 'inconclusive'
    corrupted = copy.deepcopy(records)
    corrupted[0]['result']['g_walks'][0]['reads'][0]['data'] ^= 1
    assert check(corrupted, accesses)['status'] == 'mismatch'
    if s.get('guest_switch'):
        assert [r['result']['pa'] for r in records] == [0x80200000, 0x80400000, 0x80200000]


def test_bound_c2_capture(tmp_path):
    import json
    from rvw.cosim.trace import HEX, INT, BOOL
    from rvw.regress.mmu_nested import check_c2
    s = next(s for s in matrix() if s.get('guest_switch'))
    accesses = scenario_accesses(s)
    records = [dict(access_id=i, complete=True, **{k:v for k,v in a.items() if k != 'memory'}, result=translate(**a)) for i,a in enumerate(accesses)]
    identity = dict(core='fixture', config='test', elf_sha256='a'*64, rtl_sha256='b'*64, source={}, seed=1)
    header = dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', elf='fixture', **identity)
    row = {**dict.fromkeys(HEX, '0x0'), **dict.fromkeys(INT, 0), **dict.fromkeys(BOOL, False), 'mode':3, 'mmu_nested_walks': records}
    path = tmp_path / 'capture.jsonl'
    def save(end=True):
        path.write_text('\n'.join(json.dumps(r) for r in [header,row] + ([dict(event='end',cycle=1,status='pass')] if end else [])))
    save()
    assert check_c2(path, s, identity)['status'] == 'consistent'
    assert check_c2(path, s, dict(identity, seed=2))['status'] == 'inconclusive'
    save(False)
    assert check_c2(path, s, identity)['status'] == 'inconclusive'
    row['mmu_nested_walks'][1]['result']['pa'] ^= 4096
    save()
    assert check_c2(path, s, identity)['status'] == 'mismatch'


def test_nested_coverage_observes_both_stages():
    from rvw.regress.mmu_cov import observations
    s = next(s for s in matrix() if s.get('guest_switch'))
    a = scenario_accesses(s)[0]
    record = dict(access_id=0, complete=True, **{k:v for k,v in a.items() if k != 'memory'}, result=translate(**a))
    observed = observations(dict(mmu_nested_walks=[record]))
    stages = {o['stage'] for o in observed if o['event'] == 'mmu_walk'}
    assert stages == {'vs', 'g'}
