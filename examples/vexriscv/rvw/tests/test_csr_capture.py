"""Native single-retirement CSR snapshots; no debug module in this example."""
import json
from test_adapter import compile_elf, invoke


def test_mscratch_snapshot_at_each_retirement(tmp_path):
    elf = compile_elf(tmp_path, 'csr-capture', '''
  csrwi mscratch, 7
  csrr a0, mscratch
  csrwi mscratch, 9
  csrr a1, mscratch
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
''')
    out = tmp_path/'run'
    r = invoke(['run', '--elf', elf, '--out', out, '--mem-latency', 0,
                '--max-cycles', 1000, '--rvfi-trace', '--json'])
    assert r.returncode == 0, r.stderr + r.stdout
    rows = [json.loads(line) for line in (out/'rvfi.jsonl').read_text().splitlines()]
    assert rows[0]['schema'] == 'rvw.rvfi/2'
    assert rows[0]['capabilities'] == ['csr']
    assert rows[0]['csr_snapshot'] == ['0x340']
    writes = [row for row in rows[1:] if row.get('insn') in ('0x3403d073', '0x3404d073')]
    assert [row['csr_state']['0x340'] for row in writes] == ['0x7', '0x9']
    assert all(set(row['csr_state']) == {'0x340'} for row in rows[1:] if 'order' in row)
