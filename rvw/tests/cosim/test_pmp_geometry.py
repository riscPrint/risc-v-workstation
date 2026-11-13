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


@pytest.mark.parametrize('grain', [4, 16, 4096])
def test_grain_controls_address_readback(tmp_path, tmp_path_factory, grain):
    source = tmp_path / 'grain.S'
    source.write_text('''.section .text
.globl _start
_start:
  csrw pmpcfg0, zero
  li t0, -1
  csrw pmpaddr0, t0
  csrr a0, pmpaddr0
  li t0, 0x18
  csrw pmpcfg0, t0
  csrr a1, pmpaddr0
1: j 1b
''')
    p = Platform.load('boom')
    p.pmp_granularity = grain
    model = Spike(p, _build(tmp_path_factory, source))
    try:
        reads = {}
        for _ in range(16):
            e = model.step()
            if e['rd'] in (10, 11):
                reads[e['rd']] = e['rd_wdata']
        g = grain.bit_length() - 3
        assert reads[10] & ((1 << g) - 1) == 0
        assert reads[11] & ((1 << max(0, g - 1)) - 1) == (1 << max(0, g - 1)) - 1
        if grain > 4:
            assert reads[11] != reads[10]
    finally:
        model.close()


@pytest.mark.parametrize('first_allows', [False, True])
def test_lowest_matching_entry_has_priority(tmp_path, tmp_path_factory, first_allows):
    source = tmp_path / 'priority.S'
    source.write_text('''.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  la t0, buffer
  srli t1, t0, 2
  csrw pmpaddr0, t1
  csrw pmpaddr1, t1
  li t1, ''' + ('0x989b' if first_allows else '0x9b98') + '''
  csrw pmpcfg0, t1
  sw zero, 0(t0)
  addi a0, zero, 1
handler: j handler
.section .data
.balign 16
buffer: .word 0x12345678, 0
''')
    model = Spike(Platform.load('boom'), _build(tmp_path_factory, source))
    try:
        for _ in range(24):
            e = model.step()
            if e['insn'] == 0x2a023:  # sw zero, 0(t0)
                assert bool(e['trap']) == (not first_allows)
                if not first_allows:
                    assert e['cause'] == 7
                    assert e['tval'] == model.elf.symbols['buffer']
                break
        else:
            pytest.fail('overlapping PMP store not reached')
    finally:
        model.close()
