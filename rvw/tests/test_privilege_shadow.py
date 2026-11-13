import pytest
from rvw.privilege.shadow import Stack,programs

pytestmark = pytest.mark.fast


def test_stack_model_atomic_mismatch():
    m=Stack(0x1000);m.push(42);assert m.pointer==0xff8
    with pytest.raises(ValueError,match='software check'):m.pop(43)
    assert m.pointer==0xff8
    m.pop(42);assert m.pointer==0x1000


def test_shadow_cases():
    rows=programs({'isa':'rv64im_zicfiss'})
    assert len(rows)==48
    recovery=[r for r in rows if 'readonly-recover' in r['id']]
    assert all('sfence.vma' in r['assembly'] and 'li s0, 1' in r['assembly'] for r in recovery)


def test_shadow_x5_recovery_and_guard_cases():
    rows=programs({'isa':'rv64im_zicfiss'})
    recovery=next(r['assembly'] for r in rows if r['id']=='shadow-s-readonly-recover-t0')
    assert 'mv s5, t0' in recovery and 'mv t0, s5\n mret' in recovery
    assert 'sspush t0' in recovery and 'sspopchk t0' in recovery
    guards=[r for r in rows if 'guard-' in r['id']]
    assert len(guards)==8 and all('li t1, 15' in r['assembly'] for r in guards)
    loads=[r for r in rows if 'normal-load' in r['id']]
    assert len(loads)==4 and all('ld a1, 0(a0)' in r['assembly'] for r in loads)
