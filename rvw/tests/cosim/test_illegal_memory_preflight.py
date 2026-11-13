"""Illegal RV32 encodings must reach Spike's instruction trap, not bus preflight."""
import pytest
from cosim_build import _build
from test_lockstep import plain_trace, run_check
from test_scalar_split_ram import settings

pytestmark = pytest.mark.native_light('Spike')


@pytest.mark.parametrize('encoding', [0x00003003, 0x00003023, 0x00006003])
def test_illegal_rv32_memory_encoding_traps(tmp_path_factory, tmp_path, platform, encoding):
    source = tmp_path_factory.mktemp('illegal-memory') / 'illegal.S'
    source.write_text(f'''\n.section .text
.globl _start
_start:
 la t0, handler
 csrw mtvec, t0
 .word {encoding:#x}
 li t1, 3
 j report
handler:
 csrr t0, mcause
 li t1, 2
 bne t0, t1, fail
 li t1, 1
 j report
fail:
 li t1, 3
report:
 la t0, tohost
 sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
''')
    elf = _build(tmp_path_factory, source, march='rv32i_zicsr', mabi='ilp32')
    p = settings(platform)
    rows = plain_trace(elf, p)
    trapped = [row for row in rows if row.get('trap') is True]
    assert len(trapped) == 1
    assert int(trapped[0]['insn'], 16) == encoding
    assert run_check(tmp_path, rows, elf, p)['status'] == 'match'
