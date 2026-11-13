import pytest
from rvw.formal.csr_aia_indirect import ImsicIndirectModel, UnsupportedSelection

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('xlen',[32,64])
def test_unknown_reset_and_independent_msi_observation(xlen):
    m=ImsicIndirectModel(xlen,127)
    m.select('M',0x80)
    assert m.read('M').compare(0)=='inconclusive'
    m.msi('M',5)
    assert m.read('M').compare(0)=='mismatch'
    assert m.read('M').compare(1<<5)=='inconclusive'
    m.write('M',0)
    assert m.read('M').compare(0)=='match'
    m.msi('M',5)
    assert m.read('M').compare(1<<5)=='match'
    m.msi('M',0);m.msi('M',128)
    assert m.read('M').compare(1<<5)=='match'


def test_selector_changes_route_to_distinct_banks():
    m=ImsicIndirectModel()
    m.select('M',0xc0);m.write('M',0xffffffff)
    assert m.read('M').value==0xfffffffe
    m.select('M',0x80);m.write('M',0)
    assert m.read('M').value==0
    m.select('M',0xc0)
    assert m.read('M').value==0xfffffffe
    m.select('S',0xc0)
    assert m.read('S').compare(0)=='inconclusive'


def test_guest_file_changes_use_one_vs_selector_and_separate_state():
    m=ImsicIndirectModel(64,63,2)
    m.select('VS',0xc0);m.write('VS',1<<17,guest=1)
    assert m.read('VS',guest=2).compare(0)=='inconclusive'
    m.write('VS',1<<9,guest=2)
    assert m.read('VS',guest=1).value==1<<17
    m.select('VS',0x80);m.write('VS',0,guest=1);m.msi('VS1',9)
    assert m.read('VS',guest=1).value==1<<9


def test_rv64_upper_identity_word_and_control_registers():
    m=ImsicIndirectModel(64,127)
    m.select('M',0x82);m.write('M',0);m.msi('M',100)
    assert m.read('M').compare(1<<36)=='match'
    for select,value in [(0x70,1),(0x72,63)]:
        m.select('M',select);m.write('M',value)
        assert m.read('M').compare(value)=='match'


@pytest.mark.parametrize('selector',[0,0x71,0x81,0x84,0x100])
def test_model_gaps_are_errors_not_verified_traps(selector):
    m=ImsicIndirectModel(64,63);m.select('S',selector)
    with pytest.raises(UnsupportedSelection):m.read('S')


def test_non_power_of_two_identity_capacity_keeps_legal_threshold_bits():
    m=ImsicIndirectModel(32,191);m.select('M',0x72);m.write('M',127)
    assert m.read('M').compare(127)=='match'
