import pytest
from rvw.privilege.timer32 import programs


pytestmark = pytest.mark.fast


def test_low_high_and_pending():
    rows=programs({'isa':'rv32im_zicsr_zicntr_sstc'})
    assert len(rows)==26
    assert all(' sd ' not in r['assembly'] for r in rows)
    assert all('sw zero, 4(t0)' in r['assembly'] for r in rows)
    assert 'csrw 0x15d' in rows[-1]['assembly']


def test_rv32_virtualization():
    rows=programs(dict(isa='rv32imah_zicsr_zicntr_sstc',sstc={'virtualization':True}))
    assert len(rows)==59
    assert any('csrs 0x310' in r['assembly'] for r in rows)
    assert 'csrw 0x615' in rows[-1]['assembly']


def test_rv64_rejected():
    with pytest.raises(ValueError):programs({'isa':'rv64im_zicsr_zicntr_sstc'})
