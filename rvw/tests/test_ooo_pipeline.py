from dataclasses import replace
from rvw.ooo.core import Config, Instruction, simulate


def cfg(**kw):
    return replace(Config(4, 32, 4, 64, 4, 32, 16, 16, 4,
                          {'alu': 1, 'load': 4, 'store': 2, 'divide': 10, 'branch': 1}), **kw)


def test_decode_bandwidth_limits_independent_work():
    ops = [Instruction('alu', pc=4*i) for i in range(100)]
    slow = simulate(ops, cfg(frontend={'decode_width': 1}))
    fast = simulate(ops, cfg(frontend={'decode_width': 4}))
    assert slow['cycles'] > fast['cycles'] * 2
    assert slow['topdown']['total_slots'] == slow['cycles'] * 4
    assert sum(slow['topdown']['slots'].values()) == slow['cycles'] * 4


def test_shared_execution_resources_limit_mixed_stream():
    ops = [Instruction('alu' if i % 2 else 'divide') for i in range(40)]
    shared = dict(ports={'p0': 1}, bindings={'alu': ['p0'], 'divide': ['p0']})
    a = simulate(ops, cfg(execution=shared))
    b = simulate(ops, cfg())
    assert a['cycles'] > b['cycles']
    assert a['events']['port_p0_issued'] == 40
    assert a['events']['shared_port_blocked'] > 0


def test_translation_warm_hits_and_walker_backpressure():
    translation = dict(entries=8, page_bytes=4096, hit_latency=1, walk_latency=20, walkers=1)
    ops = [Instruction('load', dest=i+1, address=i*4096, size=8) for i in range(4)]
    r = simulate(ops, cfg(translation=translation, memory_policy='disambiguate'))
    assert r['events']['page_walks'] == 4
    assert r['events']['walker_full'] > 0
    assert r['cycles'] > simulate(ops, cfg(memory_policy='disambiguate'))['cycles']


def test_forwarded_load_does_not_request_cache_service():
    class Memory:
        def __init__(self):
            self.requests = []
        def access(self, *args):
            self.requests.append(args)
            return 40
    m = Memory()
    ops = [Instruction('store', address=16, size=8), Instruction('load', dest=1, address=16, size=8)]
    r = simulate(ops, cfg(memory_policy='disambiguate'), memory=m)
    assert len(m.requests) == 1
    assert m.requests[0][2] is True
    assert r['events']['forwarded_loads'] == 1


def test_branch_recovery_slot_attribution():
    ops = [Instruction('branch', pc=0, next_pc=128)] + [Instruction('alu')] * 10
    r = simulate(ops, cfg(branch_penalty=8, frontend={'decode_width': 4}))
    assert r['topdown']['slots']['bad_speculation'] > 0
    assert r['events']['wrong_path_fetch_slots_estimate'] == 32
