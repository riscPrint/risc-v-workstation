import copy
import pytest
from rvw.cov.semantic_forms import groups, observe


def settings():
    return {'version': 1, 'forms': {'c.addi': {
        'imm': {'bits': [[12, 12, 5], [6, 2, 0]], 'width': 6, 'signed': True, 'bins': 'boundaries'},
        'rd': {'bits': [[11, 7, 0]], 'width': 5, 'bins': list(range(32))}}}}


def test_compressed_immediate_and_register_domains():
    s = settings()
    g = groups(s, [{'name': 'c.addi'}])
    assert len(g[0]['bins']) == 5
    assert len(g[1]['bins']) == 32
    plan = {'manifest': {'semantics': s}}
    for encoded, expected in [(0, 'zero'), (0x1000, 'minimum'), (0x7c, 'maximum'),
                              (4, 'positive'), (0x107c, 'negative')]:
        obs = {}
        observe(obs, plan, encoded | (3 << 7), 'c.addi')
        assert obs == {'form_imm': expected, 'form_rd': 3}


def test_split_branch_immediate_and_compact_register():
    s = {'forms': {'beq': {'imm': {'width': 13, 'signed': True, 'bins': 'boundaries',
         'bits': [[31, 31, 12], [7, 7, 11], [30, 25, 5], [11, 8, 1]]},
         'compact': {'width': 3, 'offset': 8, 'bits': [[9, 7, 0]], 'bins': list(range(8, 16))}}}}
    groups(s, [{'name': 'beq'}])
    obs = {}
    observe(obs, {'manifest': {'semantics': s}}, 0x80000000 | (7 << 7), 'beq')
    assert obs['form_imm'] == 'negative'
    assert obs['form_compact'] == 15


def test_crosses_require_complete_classifications():
    s = settings()
    cross = {'id': 'addi_rd', 'instruction': 'c.addi', 'fields': ['rd'], 'combinations': [
        {'bin': [n], 'status': 'legal' if n else 'unavailable', 'reason': 'reviewed hint domain'} for n in range(32)]}
    s['crosses'] = [cross]
    g = groups(s, [{'name': 'c.addi'}])
    assert len(g[-1]['bins']) == 32
    assert g[-1]['classifications'][0]['status'] == 'unavailable'
    cross['combinations'].pop()
    with pytest.raises(ValueError, match='not exhaustive'):
        groups(s, [{'name': 'c.addi'}])


def test_overlapping_bits_fail():
    s = settings()
    s['forms']['c.addi']['imm']['bits'].append([7, 7, 0])
    with pytest.raises(ValueError, match='overlapping'):
        groups(s, [{'name': 'c.addi'}])


def test_compressed_plan_keeps_unobserved_bins(tmp_path):
    import json
    from hashlib import sha256
    from .test_isa import source
    from rvw.cov.functional import functional
    path = source(tmp_path)
    data = json.loads(path.read_text())
    text = 'c.addi 15..13=0 1..0=1\n'
    opcode = tmp_path / 'extensions/rv_c'
    opcode.write_text(text)
    data['source']['files']['extensions/rv_c'] = sha256(text.encode()).hexdigest()
    data['semantics'] = settings()
    data['semantics']['forms']['c.addi']['rs1'] = dict(
        data['semantics']['forms']['c.addi']['rd'], bank='integer')
    path.write_text(json.dumps(data))
    trace = tmp_path / 'trace.jsonl'
    trace.write_text('\n'.join(map(json.dumps, [
        {'schema': 'rvw.rvfi/1', 'xlen': 32, 'isa': 'rv32im'},
        {'order': 0, 'insn': '0x0185', 'mode': 3, 'rd': 3, 'rs1_rdata': '0x0'}])) + '\n')
    report = functional([trace], manifest=path, source_root=tmp_path)
    assert report['groups']['form_c.addi_imm']['expected_hit'] == 1
    assert len(report['groups']['form_c.addi_rd']['holes']) == 31
    assert report['groups']['sem_c.addi_rs1']['hits'] == [{'bin': ['zero'], 'count': 1}]


def test_aligned_immediate_maximum_uses_representable_bits():
    s = {'forms': {'beq': {'imm': {'width': 13, 'signed': True, 'bins': 'boundaries',
         'bits': [[31, 31, 12], [7, 7, 11], [30, 25, 5], [11, 8, 1]]}}}}
    groups(s, [{'name': 'beq'}])
    obs = {}
    observe(obs, {'manifest': {'semantics': s}}, 0x7e000f80, 'beq')
    assert obs['form_imm'] == 'maximum'  # 4094; bit zero is implicit.
