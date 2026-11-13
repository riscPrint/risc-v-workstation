from rvw.privilege.epmp_matrix import permission,programs


def test_shared_permissions():
    assert permission(False,2,'M')==3 and permission(False,2,'S')==1
    assert permission(False,6,'U')==3
    assert permission(True,2,'M')==4 and permission(True,2,'S')==4
    assert permission(True,6,'M')==5 and permission(True,6,'U')==4
    assert permission(True,7,'M')==1 and permission(True,7,'S')==1


def test_mml_matrix():
    rows=programs({'isa':'rv64im_smepmp','epmp':{'rlb_supported':True}})
    assert len(rows)==208
    assert len({r['id'] for r in rows})==208
    assert all('li t0, 1\n csrw 0x747' in r['assembly'] for r in rows)
    assert any(r['expected_allowed'] for r in rows)
    assert any(not r['expected_allowed'] for r in rows)


def test_rlb_capability_is_explicit():
    import pytest
    with pytest.raises(ValueError,match='RLB support'):programs({'isa':'rv64im_smepmp'})
