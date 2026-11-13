from rvw.ooo.frontend import Frontend
from rvw.ooo.core import Instruction


def stream(n):
    return [Instruction('alu', pc=4*i) for i in range(n)]


def test_decode_delay_and_width():
    f = Frontend(dict(decode_width=1, decode_latency=3), 4, 16)
    ops = stream(8)
    for cycle in range(4):
        f.advance(cycle, ops)
        assert not f.ready(cycle)
    f.advance(4, ops)
    assert f.ready(4)
    assert f.pop() == ops[0]
    assert not f.ready(4)


def test_ftq_and_decode_backpressure():
    f = Frontend(dict(ftq_entries=1, block_bytes=4, decode_entries=1), 4, 16)
    for cycle in range(20):
        f.advance(cycle, stream(20))
    assert len(f.decoded) == 1
    assert len(f.fetch) == 1
    assert f.events['ftq_full'] > 0


def test_uop_cache_bypasses_decode_bandwidth():
    ops = stream(4) * 20
    def complete(entries):
        f = Frontend(dict(decode_width=1, uop_cache_entries=entries), 4, 32)
        retired = 0
        for cycle in range(1000):
            while f.ready(cycle):
                f.pop()
                retired += 1
            if retired == len(ops):
                return cycle, f.events
            f.advance(cycle, ops)
        assert False
    cold, _ = complete(0)
    warm, events = complete(4)
    assert warm < cold
    assert events['uop_cache_hits'] > 0
