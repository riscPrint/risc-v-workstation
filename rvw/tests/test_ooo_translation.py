from rvw.ooo.translation import Translation


def tlb(**kw):
    return Translation(dict(entries=2, page_bytes=4096, hit_latency=1, walk_latency=10, walkers=2, **kw))


def test_fill_completion_and_walk_coalescing():
    t = tlb()
    assert t.access(0, 8, 0) == 10
    assert t.access(8, 8, 2) == 8
    assert t.access(8, 8, 10) == 1
    assert t.events['page_walks'] == 1
    assert t.events['tlb_hits'] == 1


def test_walker_pressure_and_page_boundary():
    t = tlb()
    assert t.access(4092, 8, 0) == 10
    assert t.access(8192, 8, 1) is None
    assert t.access(8192, 8, 10) == 10
    assert t.events['page_walks'] == 3


def test_capacity_eviction():
    t = tlb()
    for i in range(3):
        assert t.access(i*4096, 8, i*20) == 10
    assert t.access(0, 8, 60) == 10
    assert len(t.tags) == 2
