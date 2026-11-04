"""CSR side effects use independent reference state at each retirement."""
import copy
import json
from cosim_build import _build
from model_fixtures import Spike
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from rvw.cosim.trace import record


def test_native_unread_csrs_and_trap(tmp_path, tmp_path_factory):
    source = tmp_path / 'unread.S'
    source.write_text('''
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  csrrwi zero, mscratch, 1
  csrrwi zero, mscratch, 2
  ecall
handler:
  nop
''')
    elf = _build(tmp_path_factory, source)
    platform = Platform.load('boom')
    addresses = ['0x300', '0x305', '0x340', '0x341', '0x342']
    header = dict(schema='rvw.rvfi/2', isa=platform.isa, xlen=64,
                  core='reference-fixture', config='test', elf=str(elf), csr_snapshot=addresses)
    model = Spike(platform, elf)
    rows = []
    try:
        for order in range(12):
            effect = model.step()
            row = record(effect, order)
            row['cycle'] = 1  # several retire slots share one cycle, each with its own state
            row.update(fd_valid=bool(effect['fd_valid']), fd=effect['fd'],
                       **{key: hex(effect[key]) for key in ('fd_wdata', 'fflags', 'fcsr')})
            row['csr_state'] = {key: hex(value) for key, value in model.csr_snapshot(addresses).items()}
            rows.append(row)
            if effect['trap']:
                assert effect['cause'] == 11
                assert row['csr_state']['0x341'] == row['pc']
                assert row['csr_state']['0x342'] == '0xb'
                break
    finally:
        model.close()
    assert rows[-1]['trap']
    writes = [r for r in rows if int(r['insn'], 16) >> 20 == 0x340]
    assert [r['csr_state']['0x340'] for r in writes] == ['0x1', '0x2']
    assert all(int(r['insn'], 16) & 0x7f != 0x73 or r['rd'] == 0 for r in rows)
    path = tmp_path / 'csr.jsonl'
    def compare(records):
        path.write_text(''.join(json.dumps(r)+'\n' for r in [header, *records]))
        reference = Spike(platform, elf)
        try:
            return check(path, reference, platform)
        finally:
            reference.close()
    assert compare(rows)['status'] == 'match'
    changed = copy.deepcopy(rows)
    first = rows.index(writes[0])
    changed[first]['csr_state']['0x340'] = '0x2'  # final cycle state used too early
    result = compare(changed)
    assert result['mismatch']['order'] == first
    assert 'csr[0x340]' in result['mismatch']['differences']
    changed = copy.deepcopy(rows)
    changed[-1]['csr_state']['0x341'] = '0x0'
    assert 'csr[0x341]' in compare(changed)['mismatch']['differences']
