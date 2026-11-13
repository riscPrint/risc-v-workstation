import pytest
from rvw.privilege.epmp import programs


pytestmark = pytest.mark.fast


def test_policy_matrix():
    rows = programs({'isa': 'rv64im_smepmp'})
    assert len(rows) == 4
    assert {r['id'] for r in rows} == {'epmp-mmwp', 'epmp-mml-su', 'epmp-mml-m', 'epmp-rlb'}
    assert all('csrw 0x747' in r['assembly'] for r in rows)
    assert 'addi t0, s0, 4' in rows[-1]['assembly']


def test_requires_extension():
    with pytest.raises(ValueError): programs({'isa': 'rv64im'})
