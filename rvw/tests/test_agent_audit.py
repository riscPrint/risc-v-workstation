"""Admission of actual artifacts, with small synthetic C1/C2 inputs for tests."""
import hashlib
import json
import pytest
from rvw.agent_bench.audit import audit_run
from rvw.cosim.trace import HEX, INT, BOOL

pytestmark = pytest.mark.fast


@pytest.fixture
def inputs(tmp_path):
    elf = tmp_path / 'program'
    elf.write_bytes(b'unit test input')
    identity = {'rtl_sha256': 'a' * 64, 'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
                'source': {'core_rev': 'c' * 40}, 'seed': 1, 'config': 'default'}
    (tmp_path / 'result.json').write_text(json.dumps({'schema': 'rvw.run/1', 'status': 'pass', **identity}))
    header = {'schema': 'rvw.rvfi/1', 'xlen': 32, 'isa': 'rv32i', 'core': 'unit', 'elf': str(elf), **identity}
    row = {**{k: '0x0' for k in HEX}, **{k: 0 for k in INT}, **{k: False for k in BOOL}, 'mode': 3}
    lines = [header, row, {'event': 'end', 'cycle': 1, 'status': 'pass'}]
    (tmp_path / 'rvfi.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in lines))
    return tmp_path, elf, lines


def test_admits_consistent_pair_but_never_claims_repair(inputs):
    root, elf, _ = inputs
    result = audit_run(root, elf, expected_identity={'rtl_sha256': 'a' * 64})
    assert result['status'] == 'evidence_consistent'
    assert result['repair'] == 'NOT CLAIMED'
    assert result['task_identity_fields'] == ['rtl_sha256']


@pytest.mark.parametrize('defect', ['stale', 'elf', 'unsupported', 'coverage', 'end'])
def test_misleading_inputs_remain_inconclusive(inputs, defect):
    root, elf, lines = inputs
    kwargs = {}
    if defect == 'stale': kwargs['expected_identity'] = {'rtl_sha256': 'b' * 64}
    if defect == 'elf': elf.write_bytes(b'wrong program')
    if defect == 'unsupported': lines[0]['capabilities'] = ['unsupported']
    if defect == 'coverage': kwargs['required_artifacts'] = ['coverage.dat']
    if defect == 'end': lines.pop()
    (root / 'rvfi.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in lines))
    result = audit_run(root, elf, **kwargs)
    assert result['status'] == 'inconclusive' and result['problems']
    assert result['repair'] == 'NOT CLAIMED'
