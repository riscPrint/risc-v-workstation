"""Native M-only adapter CSR legality, independent of reference masks."""
import json
from test_adapter import compile_elf, invoke


def test_supervisor_csr_traps(tmp_path):
    elf = compile_elf(tmp_path, 'satp', '''
  la t0, handler
  csrw mtvec, t0
  csrwi satp, 0
  li t1, 3
  j report
handler:
  csrr t0, mcause
  li t1, 2
  bne t0, t1, fail
  li t1, 1
  j report
fail:
  li t1, 5
report:
  la t0, tohost
  sw t1, 0(t0)
''')
    out = tmp_path/'run'
    r = invoke(['run', '--elf', elf, '--out', out, '--mem-latency', 0,
                '--max-cycles', 1000, '--rvfi-trace', '--json'])
    assert r.returncode == 0, r.stderr + r.stdout
    rows = [json.loads(line) for line in (out/'rvfi.jsonl').read_text().splitlines()]
    assert any(row.get('event') == 'trap' and row['cause'] == '0x2' for row in rows)
