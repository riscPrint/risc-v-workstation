"""Directed Spike state checks. These are reference tests, not DUT captures."""
import pytest
from cosim_build import _build
from model_fixtures import Spike
from rvw.cosim.platform import Platform


@pytest.mark.parametrize('rounding,positive,negative', [
    ('rne', 0x3f800000, 0xbf800000),
    ('rtz', 0x3f800000, 0xbf800000),
    ('rdn', 0x3f800000, 0xbf800001),
    ('rup', 0x3f800001, 0xbf800000),
    ('rmm', 0x3f800001, 0xbf800001),
    ('dyn', 0x3f800001, 0xbf800000),  # frm=RUP
])
def test_spike_halfway_rounding(tmp_path, tmp_path_factory, rounding, positive, negative):
    source = tmp_path / 'rounding.S'
    source.write_text(f'''
.section .text
.globl _start
_start:
  li t0, 0x6000
  csrs mstatus, t0
  li t0, 0x3f800000
  fmv.w.x f0, t0
  li t0, 0x33800000
  fmv.w.x f1, t0
  li t0, 0xbf800000
  fmv.w.x f2, t0
  li t0, 0xb3800000
  fmv.w.x f3, t0
  csrrwi zero, frm, 3
  fadd.s f4, f0, f1, {rounding}
  fadd.s f5, f2, f3, {rounding}
  nop
''')
    model = Spike(Platform.load('boom'), _build(tmp_path_factory, source, march='rv64imafdc_zicsr'))
    results = {}
    try:
        for _ in range(24):
            effect = model.step()
            if effect['fd_valid'] and effect['fd'] in (4, 5):
                results[effect['fd']] = effect
            if len(results) == 2:
                break
    finally:
        model.close()
    assert results[4]['fd_wdata'] == 0xffffffff00000000 | positive
    assert results[5]['fd_wdata'] == 0xffffffff00000000 | negative
    assert results[4]['fflags'] == results[5]['fflags'] == 1  # NX
    assert results[5]['fcsr'] == 0x61  # frm=RUP and accrued NX


def test_spike_nan_boxing_and_signaling_nan(tmp_path, tmp_path_factory):
    source = tmp_path / 'nan.S'
    source.write_text('''
.section .text
.globl _start
_start:
  li t0, 0x6000
  csrs mstatus, t0
  li t0, 0x7f800001
  fmv.w.x f0, t0
  fadd.s f1, f0, f0
  li t0, 0x3f800000
  fmv.d.x f2, t0
  fadd.s f3, f2, f2
  nop
''')
    model = Spike(Platform.load('boom'), _build(tmp_path_factory, source, march='rv64imafdc_zicsr'))
    results = {}
    try:
        for _ in range(20):
            effect = model.step()
            if effect['fd_valid']:
                results[effect['fd']] = effect
            if 3 in results:
                break
    finally:
        model.close()
    assert results[0]['fd_wdata'] == 0xffffffff7f800001  # payload retained by move
    assert results[1]['fd_wdata'] == 0xffffffff7fc00000
    assert results[1]['fflags'] == 16  # signaling NaN sets NV
    assert results[2]['fd_wdata'] == 0x3f800000  # deliberately unboxed single
    assert results[3]['fd_wdata'] == 0xffffffff7fc00000
    assert results[3]['fflags'] == 16  # unboxed operand becomes quiet NaN


def test_spike_fp_dirty_transitions(tmp_path, tmp_path_factory):
    source = tmp_path / 'dirty.S'
    source.write_text('''
.section .text
.globl _start
_start:
  li t0, 0x2000
  csrw mstatus, t0
  fmv.w.x f0, zero
  li t0, 0x4000
  csrw mstatus, t0
  fadd.s f1, f0, f0
  nop
''')
    model = Spike(Platform.load('boom'), _build(tmp_path_factory, source, march='rv64imafdc_zicsr'))
    states = []
    try:
        for _ in range(16):
            effect = model.step()
            if effect['insn'] == 0x30029073 or effect['fd_valid']:
                states.append((model.csr_snapshot(['0x300'])['0x300'] >> 13) & 3)
            if len(states) == 4:
                break
    finally:
        model.close()
    assert states == [1, 3, 2, 3]  # Initial -> Dirty; Clean -> Dirty
