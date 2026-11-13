"""RTL trace ingress from the rv32im_trace configuration, checked against C2 (needs VEXRISCV and native tools)."""
import json
import os
from pathlib import Path

import pytest

from rvw.debug import ingress_check
from test_adapter import compile_elf, invoke

EXAMPLE = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not os.environ.get('VEXRISCV'), reason='VEXRISCV checkout not set')


def test_ingress_matches_c2_with_branches_and_ecall(tmp_path):
    elf = compile_elf(tmp_path, 'flow', '''la t0, handler
csrw mtvec, t0
li t1, 4
2: addi t1, t1, -1
bnez t1, 2b
ecall
la t1, tohost
li t2, 1
sw t2, 0(t1)
3: j 3b
.align 2
handler:
csrr t0, mepc
addi t0, t0, 4
csrw mepc, t0
mret''')
    out = tmp_path / 'run'
    invoke(['run', '--config', 'rv32im_trace', '--elf', elf, '--out', out, '--seed', 1, '--mem-latency', 0,
            '--rvfi-trace', '--trace-ingress', EXAMPLE / 'trace/ingress-binding.json'])
    assert json.loads((out / 'result.json').read_text())['status'] == 'pass'
    result = ingress_check.check(out / 'te_ingress.csv', out / 'rvfi.jsonl', elf)
    assert result['status'] == 'match', result
    assert result['rebuilt_trap_rows'] == 1
