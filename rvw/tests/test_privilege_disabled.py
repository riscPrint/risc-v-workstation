"""Disabled-state matrix checks, without native tools."""
import pytest
from rvw.privilege.disabled import programs


def test_fs_off():
    rows = programs({'isa': 'rv64imf_zicsr'})
    assert len(rows) == 36
    assert len({r['id'] for r in rows}) == len(rows)
    assert all('fmv.w.x f0, zero' in r['assembly'] for r in rows)
    assert all('li t0, 0x6000\n csrc mstatus' in r['assembly'] for r in rows)


def test_absent_s():
    rows = programs({'priv': 'mu'})
    assert len(rows) == 72
    for r in rows:
        assert 'csrw satp, zero' not in r['assembly']
        assert 'csrw medeleg' not in r['assembly']
        assert 'li t1, 2' in r['assembly']
        assert 'bne t0, t1, fail' in r['assembly']


def test_fs_needs_f():
    with pytest.raises(ValueError, match='requires an ISA with F'):
        programs({'isa': 'rv64im_zicsr'})
