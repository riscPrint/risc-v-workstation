"""Native capture inventory and write/read timing for the full machine CSR set."""
import json
from test_adapter import compile_elf, invoke


def test_full_machine_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_VEX_CSR_FULL', '1')
    elf = compile_elf(tmp_path, 'full-csr', '''
  csrwi mscratch, 7
  csrwi mscratch, 9
  csrr a0, mscratch
  li t0, 0x80000100
  csrw mtvec, t0
  csrr a1, mtvec
  li t0, 0x80000200
  csrw mepc, t0
  csrr a2, mepc
  csrwi mtval, 11
  csrr a3, mtval
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
''')
    out = tmp_path/'run'
    result = invoke(['run', '--elf', elf, '--out', out, '--mem-latency', 0,
                     '--max-cycles', 1000, '--rvfi-trace', '--json'])
    assert result.returncode == 0, result.stderr + result.stdout
    rows = [json.loads(l) for l in (out/'rvfi.jsonl').read_text().splitlines()]
    expected = {'0x300', '0x301', '0x304', '0x305', '0x340', '0x341', '0x342',
                '0x343', '0x344', '0xb00', '0xb80', '0xb02', '0xb82',
                '0xf11', '0xf12', '0xf13', '0xf14'}
    assert set(rows[0]['csr_snapshot']) == expected
    retired = [r for r in rows if 'order' in r]
    assert all(set(r['csr_state']) == expected for r in retired)
    # C2 is post-retirement state, including the edge which fired this RVFI slot.
    assert all(int(r['csr_state']['0xb00'], 16) == r['cycle'] for r in retired)
    assert all(int(r['csr_state']['0xb02'], 16) == r['order'] + 1 for r in retired)
    writes = [r for r in retired if r['insn'] in ('0x3403d073', '0x3404d073')]
    assert [int(r['csr_state']['0x340'], 16) for r in writes] == [7, 9]
    for rd, address, value in [(10, '0x340', 9), (11, '0x305', 0x80000100),
                               (12, '0x341', 0x80000200), (13, '0x343', 11)]:
        row = next(r for r in retired if r['rd'] == rd)
        assert int(row['rd_wdata'], 16) == value
        assert int(row['csr_state'][address], 16) == value
    assert [int(retired[0]['csr_state'][a], 16) for a in ('0xf11', '0xf12', '0xf13', '0xf14')] == [11, 22, 33, 0]
