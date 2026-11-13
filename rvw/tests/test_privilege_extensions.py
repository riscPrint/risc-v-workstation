import pytest
from rvw.privilege.extensions import programs


@pytest.mark.parametrize('kind,isa,count', [('sstc','rv64im_zicsr_zicntr_sstc',13),
    ('stateen','rv64im_zicsr_smstateen',6), ('landing','rv64im_zicsr_zicfilp',12)])
def test_matrices(kind, isa, count):
    rows = programs(dict(kind=kind, isa=isa))
    assert len(rows) == count
    assert len({r['id'] for r in rows}) == count
    assert all('spec' in r for r in rows)


def test_environment_mask():
    assert len(programs(dict(kind='envcfg',isa='rv64im_zicsr',envcfg={'implemented_mask':1}))) == 6
    with pytest.raises(ValueError):
        programs(dict(kind='envcfg',isa='rv64im_zicsr',envcfg={'implemented_mask':0}))


def test_virtual_timer_matrix():
    assert len(programs(dict(kind='sstc',isa='rv64imah_zicsr_zicntr_sstc',sstc={'virtualization':True})))==29


def test_sstc_needs_time():
    with pytest.raises(ValueError,match='Zicntr'):programs(dict(kind='sstc',isa='rv64im_sstc'))
