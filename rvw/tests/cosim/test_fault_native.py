"""Reference-only zero-completion faults, with independently specified attempts."""
import copy
import json

import pytest
from cosim_build import _build
from model_fixtures import Spike
from rvw.cosim.platform import Platform
from rvw.cosim.trace import record
from rvw.cosim.checker import check


@pytest.mark.parametrize('opcode,read,write,cause', [
    ('lbu a0, 0(t0)', 1, 0, 5),
    ('lhu a0, 0(t0)', 3, 0, 5),
    ('lwu a0, 0(t0)', 15, 0, 5),
    ('sd zero, 0(t0)', 0, 255, 7),
    ('lr.w a0, (t0)', 15, 0, 5),
    ('amoadd.w a0, zero, (t0)', 15, 15, 7),
])
def test_native_fault_attempt(tmp_path, tmp_path_factory, opcode, read, write, cause):
    source = tmp_path / 'fault.S'
    source.write_text('''.section .text
.globl _start
_start:
  la t1, handler
  csrw mtvec, t1
  li t0, 0x10000000
''' + opcode + '''
handler: j handler
''')
    elf = _build(tmp_path_factory, source)
    p = Platform.load('boom')
    model = Spike(p, elf)
    rows = []
    try:
        for order in range(16):
            effect = model.step()
            row = record(effect, order)
            row.update(fd_valid=bool(effect['fd_valid']), fd=effect['fd'],
                       **{k: hex(effect[k]) for k in ('fd_wdata', 'fflags', 'fcsr')})
            rows.append(row)
            if effect['trap']:
                assert effect['cause'] == cause
                assert effect['tval'] == 0x10000000
                assert effect['mem_rmask'] == effect['mem_wmask'] == 0
                break
        else:
            pytest.fail('fault was not reached')
    finally:
        model.close()
    rows[-1]['fault_access'] = dict(addr='0x10000000', rmask=read, wmask=write,
        completed_rmask=0, completed_wmask=0, rdata=None, wdata=None)
    header = dict(schema='rvw.rvfi/2', xlen=64, isa=p.isa, core='reference-only',
                  config='test', elf=str(elf))
    path = tmp_path / 'trace.jsonl'
    def compare(records):
        path.write_text(''.join(json.dumps(r)+'\n' for r in [header, *records]))
        reference = Spike(p, elf)
        try:
            return check(path, reference, p)
        finally:
            reference.close()
    result = compare(rows)
    assert result['status'] == 'match'
    assert result['state_coverage']['fault_access_steps'] == 1
    changed = copy.deepcopy(rows)
    changed[-1]['fault_access']['addr'] = '0x10000004'
    assert 'fault_access.addr' in compare(changed)['mismatch']['differences']
    changed = copy.deepcopy(rows)
    changed[-1]['fault_access'].update(completed_wmask=1, wmask=write or 1, wdata='0x0')
    with pytest.raises(ValueError, match='partial fault'):
        compare(changed)


@pytest.mark.parametrize('policy', ['trap', 'emulate'])
@pytest.mark.parametrize('opcode,alignment,access', [('lw a0, 0(t0)', 4, 5), ('sw zero, 0(t0)', 6, 7)])
def test_misaligned_unmapped_fault_precedence(tmp_path, tmp_path_factory, policy, opcode, alignment, access):
    source = tmp_path / 'precedence.S'
    source.write_text('''.section .text
.globl _start
_start:
  la t1, handler
  csrw mtvec, t1
  li t0, 0x10000001
''' + opcode + '''
handler: j handler
''')
    elf = _build(tmp_path_factory, source)
    p = Platform.load('boom')
    p.misaligned.update(load=policy, store=policy, atomic='trap' if policy == 'trap' else 'access_fault')
    reference = Spike(p, elf)
    try:
        for _ in range(16):
            effect = reference.step()
            if effect['trap']:
                assert effect['cause'] == (alignment if policy == 'trap' else access)
                assert effect['tval'] == 0x10000001
                assert effect['mem_rmask'] == effect['mem_wmask'] == 0
                break
        else:
            pytest.fail('unmapped misaligned access did not fault')
    finally:
        reference.close()
