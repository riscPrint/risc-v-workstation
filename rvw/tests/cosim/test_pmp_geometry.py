"""Native reference checks for locked PMP encodings; no DUT coverage claim."""
import pytest
from cosim_build import _build
from model_fixtures import Spike
from rvw.cosim.platform import Platform


@pytest.mark.parametrize('encoding', ['tor', 'na4', 'napot'])
def test_locked_pmp_region_denies_store(tmp_path, tmp_path_factory, encoding):
    # Each program allows reads but denies writes. Locked regions apply to M.
    setup = {
        'tor': '''srli t1, t0, 2
  csrw pmpaddr0, t1
  addi t1, t1, 2
  csrw pmpaddr1, t1
  li t1, 0x8900''',
        'na4': '''srli t1, t0, 2
  csrw pmpaddr0, t1
  li t1, 0x91''',
        'napot': '''srli t1, t0, 2
  csrw pmpaddr0, t1
  li t1, 0x99''',
    }[encoding]
    source = tmp_path / 'pmp.S'
    source.write_text('''.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  la t0, buffer
  ''' + setup + '''
  csrw pmpcfg0, t1
  csrw pmpcfg0, zero
  csrw pmpaddr0, zero
  csrw pmpaddr1, zero
  lw a0, 0(t0)
  sw zero, 0(t0)
handler: j handler
.section .data
.balign 16
buffer: .word 0x12345678, 0
''')
    elf = _build(tmp_path_factory, source)
    p = Platform.load('boom')
    model = Spike(p, elf)
    try:
        read = None
        for _ in range(32):
            effect = model.step()
            if effect['rd'] == 10:
                read = effect['rd_wdata']
            if effect['trap']:
                assert read == 0x12345678
                assert effect['cause'] == 7
                assert effect['tval'] == model.elf.symbols['buffer']
                assert model.csr_snapshot(['0x3a0'])['0x3a0'] == {'tor': 0x8900, 'na4': 0x91, 'napot': 0x99}[encoding]
                break
        else:
            pytest.fail('locked PMP store did not fault')
    finally:
        model.close()
