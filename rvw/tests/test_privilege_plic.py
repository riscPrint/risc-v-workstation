from rvw.privilege.plic import programs


def rows():
    return programs({'plic': dict(priority=0xc000000, pending=0xc001000,
        enable=0xc002000, enable_stride=0x80, context=0xc200000,
        context_stride=0x1000, sources=2, contexts=2)})


def test_arbitration_and_gateway():
    r = {r['id']: r for r in rows()}
    assert r['plic-tie']['expected_claims'] == [1, 2]
    assert r['plic-priority']['expected_claims'] == [2, 1]
    assert r['plic-threshold-claim']['expected_claims'] == [1]
    assert r['plic-contexts']['expected_claims'] == [1, 0]
    assert r['plic-gateway']['expected_claims'] == [1, 1, 0]
    assert r['plic-disabled']['expected_claims'] == [0, 1]
    for row in r.values():
        assert 'stimulus_ack' in row['assembly']
        assert row['events']
