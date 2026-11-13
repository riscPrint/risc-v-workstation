from rvw.privilege.pmp import programs, program


def test_matrix():
    rows = programs({})
    assert len(rows) == 394
    assert len({r['id'] for r in rows}) == len(rows)
    assert all('csrw pmpcfg0, zero' in r['assembly'] for r in rows)


def test_lock_and_mprv():
    s = program('tor', 'mprv-s', True, 0, 'read')
    assert 'csrw pmpaddr1, zero' in s
    assert 'csrw pmpaddr0, zero' in s
    assert 'csrr t0, mtval' in s
    assert 'li t1, 5' in s


def test_machine_bypass_and_priority():
    assert 'li t1, 11' in program('napot', 'M', False, 0, 'write')
    assert 'li t1, 7' in program('napot', 'M', True, 0, 'write')
    assert 'li t1, 5' in program('napot', 'S', False, 7, 'read', priority=True)
