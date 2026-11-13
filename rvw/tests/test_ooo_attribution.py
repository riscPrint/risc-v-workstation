from rvw.ooo.attribution import Attribution


def test_slot_partition_and_precedence():
    a = Attribution(4)
    a.observe(2, True, True)
    a.observe(1, False, True)
    a.observe(0, False, False)
    r = a.report()
    assert r['total_slots'] == 12
    assert r['slots'] == dict(retiring=3, bad_speculation=2, backend_bound=3, frontend_bound=4)
    assert sum(r['fractions'].values()) == 1
