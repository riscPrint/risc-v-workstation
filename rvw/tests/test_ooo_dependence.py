from types import SimpleNamespace
from rvw.ooo.core import Instruction
from rvw.ooo.dependence import Dependence, overlaps


def test_training_and_bounded_pairs():
    p = Dependence(1)
    a = Instruction('load', pc=8, address=16, size=8)
    b = Instruction('store', pc=4, address=20, size=8)
    assert overlaps(a, b)
    assert not p.waits(a, b)
    entry = SimpleNamespace(insn=a, done=4)
    assert p.violations(b, [entry]) == [entry]
    assert p.waits(a, b)
    p.train(Instruction('load', pc=12), b)
    assert not p.waits(a, b)
    assert len(p.pairs) == 1


def test_alias_replay_reexecutes_consumers_and_trains():
    from rvw.ooo.core import Config, simulate
    c = Config(4, 16, 4, 64, 4, 32, 16, 16, 4,
               {'alu': 1, 'divide': 12, 'load': 4, 'store': 2}, memory_policy='speculate')
    iteration = [Instruction('divide', (), 1, pc=0),
                 Instruction('store', (1,), pc=4, address=16, size=8),
                 Instruction('load', (), 2, pc=8, address=16, size=8),
                 Instruction('alu', (2,), 3, pc=12)]
    r = simulate(iteration * 2, c)
    assert r['instret'] == 8
    assert r['events']['speculative_loads'] > 0
    assert r['events']['memory_order_replays'] == 1
    assert r['events']['issued'] > 8
    assert r['events']['store_address_blocked'] > 0
    assert r['topdown']['slots']['bad_speculation'] > 0


def test_nonalias_speculation_avoids_wait_without_replay():
    from dataclasses import replace
    from rvw.ooo.core import Config, simulate
    c = Config(4, 16, 4, 32, 4, 16, 8, 8, 4,
               {'alu': 1, 'divide': 12, 'load': 20, 'store': 2}, memory_policy='speculate')
    ops = [Instruction('divide', (), 1), Instruction('store', (1,), address=16, size=8),
           Instruction('load', (), 2, address=128, size=8)]
    r = simulate(ops, c)
    assert not r['events'].get('memory_order_replays')
    assert r['cycles'] < simulate(ops, replace(c, memory_policy='disambiguate'))['cycles']


def test_memory_service_requests_are_in_cycle_order():
    from rvw.ooo.core import Config, simulate
    class Memory:
        def __init__(self): self.cycles = []
        def access(self, address, size, write, cycle):
            self.cycles.append(cycle)
            return 1
    m = Memory()
    c = Config(4, 16, 4, 32, 4, 16, 16, 16, 4, {'load': 1},
               memory_policy='disambiguate', translation=dict(entries=4, page_bytes=4096,
               hit_latency=1, walk_latency=10, walkers=2))
    ops = [Instruction('load', (), i+1, address=i*4096, size=8) for i in range(4)]
    simulate(ops, c, memory=m)
    assert m.cycles == sorted(m.cycles)
    assert len(m.cycles) == 4
