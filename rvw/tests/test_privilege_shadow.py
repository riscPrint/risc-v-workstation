import pytest
from rvw.privilege.shadow import Stack,programs


def test_stack_model_atomic_mismatch():
    m=Stack(0x1000);m.push(42);assert m.pointer==0xff8
    with pytest.raises(ValueError,match='software check'):m.pop(43)
    assert m.pointer==0xff8
    m.pop(42);assert m.pointer==0x1000


def test_shadow_cases():
    rows=programs({'isa':'rv64im_zicfiss'})
    assert len(rows)==12
    recovery=[r for r in rows if 'readonly-recover' in r['id']]
    assert all('sfence.vma' in r['assembly'] and 'li s0, 1' in r['assembly'] for r in recovery)
