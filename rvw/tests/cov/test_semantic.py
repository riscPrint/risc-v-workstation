import json
import pytest
from rvw.cov.semantic import Observer, groups, value_class


def test_value_classes_and_unknown_data():
    assert [value_class(v, 32) for v in (0, 1, 0xffffffff, 0x80000000, 0x7fffffff, 2, 0x80000001)] == [
        'zero', 'one', 'all_ones', 'signed_min', 'signed_max', 'other_positive', 'other_negative']
    with pytest.raises(ValueError):
        value_class(-1, 32)


def test_semantic_plan_keeps_unseen_bins(tmp_path):
    from .test_isa import source
    from rvw.cov.functional import functional
    p = source(tmp_path)
    data = json.loads(p.read_text())
    data['semantics'] = {'version': 1, 'exceptions': {'add': [2]}, 'privilege_modes': ['M', 'U']}
    p.write_text(json.dumps(data))
    trace = tmp_path / 'sem.jsonl'
    rows = [dict(schema='rvw.rvfi/1', xlen=32, isa='rv32im'),
            dict(order=0, cycle=1, insn='0x002081b3', rd=3, mode=3, rs1_rdata='0x0', rs2_rdata='0xffffffff'),
            dict(order=1, cycle=2, insn='0x002081b3', rd=0, mode=0, trap=True),
            dict(event='trap', cycle=2, cause='0x2', intr=False)]
    trace.write_text('\n'.join(map(json.dumps, rows))+'\n')
    r = functional([trace], manifest=p, source_root=tmp_path)
    assert r['groups']['sem_add_rs1']['expected_bins'] == 7
    assert r['groups']['sem_add_rs1']['hits'] == [{'bin': ['zero'], 'count': 1}]
    assert r['groups']['sem_add_exception']['expected_hit'] == 1
    assert r['groups']['sem_privilege_transition']['holes'] == [['U', 'M']]
    rows[-1]['cycle'] = 3
    trace.write_text('\n'.join(map(json.dumps, rows))+'\n')
    r = functional([trace], manifest=p, source_root=tmp_path)
    assert r['groups']['sem_add_exception']['expected_hit'] == 0


def test_semantics_do_not_invent_exception_causes_or_fp_operands():
    insns = [{'name': 'fadd.s', 'args': ['rs1', 'rs2'], 'source': 'extensions/rv_f'}]
    g = groups({'semantics': {'version': 1}}, insns)
    assert [x['name'] for x in g] == ['sem_privilege_transition']
    with pytest.raises(ValueError, match='not in pinned'):
        groups({'semantics': {'version': 1, 'exceptions': {'unknown': [2]}}}, insns)


def test_semantic_csr_legal_access_domains_and_immediates():
    insns = [{'name': n, 'args': ['rd', 'rs1', 'imm12'], 'source': 'extensions/rv_zicsr'}
             for n in ('csrrw', 'csrrs')]
    g = {x['name']: x for x in groups({'semantics': {'version': 1}}, insns)}
    assert g['sem_csrrw_access']['bins'] == [['read_write'], ['write']]
    assert g['sem_csrrs_access']['bins'] == [['read_write'], ['read']]
    obs = {'event': 'retire', 'mode': 'M', 'order': 0, 'isa_imm12': 2048}
    Observer().observe({'order': 0}, [obs], {'manifest': {'semantics': {}}}, 32)
    assert obs['imm12_class'] == 'minimum'


def test_ambiguous_same_cycle_faults_earn_no_exception_hit():
    o = Observer()
    plan = {'manifest': {'semantics': {}}}
    for order in (0, 1):
        row = dict(order=order, cycle=2, trap=True)
        o.observe(row, [dict(row, mode='M', fault_instruction='add')], plan, 32)
    assert o.observe(dict(event='trap', cycle=2, cause='0x2'), [], plan, 32) == []


def test_semantic_plan_change_requires_spec_adoption(tmp_path):
    from .test_isa import source
    from rvw.cov.isa import spec_diff
    before_dir, after_dir = tmp_path / 'a', tmp_path / 'b'
    before_dir.mkdir()
    after_dir.mkdir()
    before, after = source(before_dir), source(after_dir)
    data = json.loads(after.read_text())
    data['semantics'] = {'version': 1}
    after.write_text(json.dumps(data))
    r = spec_diff(before, after, before_dir, after_dir)
    assert r['adoption_required']
    assert 'semantics' in r['declarations']


def test_csr_access_intent_does_not_depend_on_reported_writeback():
    from rvw.cov.functional import observations
    # CSRRW x1,mstatus,x0 requests a read even if the trace reports no writeback.
    obs, _ = observations({'order': 0, 'insn': '0x300010f3', 'rd': 0, 'mode': 3}, 32, None)
    assert obs[0]['csr_access'] == 'read_write'
    # CSRRW x0,mstatus,x0 suppresses the read by encoding.
    obs, _ = observations({'order': 0, 'insn': '0x30001073', 'rd': 1, 'mode': 3}, 32, None)
    assert obs[0]['csr_access'] == 'write'
