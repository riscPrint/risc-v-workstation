from dataclasses import replace
import pytest
from rvw.ooo.core import Config, Instruction, simulate

pytestmark = pytest.mark.fast


def config(**kwargs):
    return Config(2, 8, 2, 16, 2, 8, 2, 2, 2,
                  dict(alu=1, branch=10, load=2, store=2), **kwargs)


def test_mix_occupancy_is_bounded_and_squashed():
    ops = [Instruction('branch', pc=0, next_pc=100)] + [
        Instruction('load', address=128, size=4, pc=100+4*i, next_pc=104+4*i) for i in range(10)]
    result = simulate(ops, config(wrong_path_occupancy=True), backend='python')
    assert result['instret'] == len(ops)
    assert result['events']['wrong_path_renamed'] > 0
    assert result['events']['wrong_path_squashed'] == result['events']['wrong_path_renamed']
    assert result['max_occupancy']['load_entries'] <= 2
    assert result['max_occupancy']['rob_entries'] <= 16
    assert result['events'].get('wrong_path_load_requests', 0) == 0


def test_wrong_occupancy_flag_is_boolean():
    with pytest.raises(ValueError, match='wrong_path_occupancy'):
        config(wrong_path_occupancy=1)


def test_wrong_path_allocates_while_branch_waits_for_operand():
    ops = [Instruction('load', dest=1, address=128, size=4),
           Instruction('branch', sources=(1,), pc=4, next_pc=100),
           Instruction('alu', pc=100, next_pc=104)]
    c = replace(config(wrong_path_occupancy=True), latencies=dict(alu=1, branch=2, load=20, store=2))
    result = simulate(ops, c, backend='python')
    # A two-cycle branch alone cannot admit this many operations. Its operand
    # wait must also contribute speculative queue occupancy.
    assert result['events']['wrong_path_renamed'] > c.fetch_width * c.latencies['branch']
    assert result['events']['wrong_path_squashed'] == result['events']['wrong_path_renamed']


def test_prediction_ticket_survives_multiple_renamed_branches():
    class Predictor:
        def __init__(self): self.pending = None; self.last_delay = 0; self.updated = []
        def predict_instruction(self, op):
            self.pending = op.pc
            return op.next_pc
        def update_instruction(self, op):
            assert self.pending == op.pc
            self.updated.append(op.pc)
            self.pending = None
    ops = [Instruction('branch', pc=i*4, next_pc=i*4+4) for i in range(8)]
    predictor = Predictor()
    result = simulate(ops, config(wrong_path_occupancy=True, branch_speculation=True), backend='python', predictor=predictor)
    assert result['instret'] == 8
    assert predictor.updated == [i*4 for i in range(8)]


def test_correct_predictions_do_not_add_a_fetch_guard():
    ops = [Instruction('branch', pc=4*i, next_pc=4*i+4) for i in range(12)]
    c = config(branch_speculation=True, frontend=dict(decode_width=2, decode_entries=8, decode_latency=2, fetch_latency=3))
    original = simulate(ops, c, backend='python')
    occupancy = simulate(ops, replace(c, wrong_path_occupancy=True), backend='python')
    assert occupancy['cycles'] <= original['cycles']
    assert occupancy['events'].get('wrong_path_renamed', 0) == 0


class SlowStores:
    def __init__(self):
        self.requests = []
    def access(self, address, size, write, cycle):
        self.requests.append((address, write, cycle))
        return 12 if write else 0


def test_drain_retains_store_slots_and_backpressures_rename():
    ops = [Instruction('store', address=128+4*i, size=4) for i in range(8)]
    memory = SlowStores()
    c = config(store_policy='buffered', memory_policy='disambiguate', store_drain_width=1)
    finite = simulate(ops, c, memory=memory, backend='python')
    unlimited = simulate(ops, replace(c, store_drain_width=0), memory=SlowStores(), backend='python')
    assert finite['cycles'] > unlimited['cycles']
    assert finite['events']['store_full'] > 0
    assert finite['events']['store_drain_blocked'] > 0
    assert finite['max_occupancy']['store_entries'] <= c.store_entries
    assert all(write for _,write,_ in memory.requests)


def test_load_forwards_from_committed_undrained_store():
    ops = [Instruction('store', address=128, size=4)] + [Instruction('alu') for _ in range(8)] + [Instruction('load', address=128, size=4)]
    memory = SlowStores()
    c = config(store_policy='buffered', memory_policy='disambiguate', store_drain_width=1)
    result = simulate(ops, c, memory=memory, backend='python')
    assert result['events']['forwarded_loads'] == 1
    assert not any(not write for _,write,_ in memory.requests)


def test_drain_requires_buffered_policy():
    with pytest.raises(ValueError, match='buffered'):
        config(store_drain_width=1)


def test_partial_overlap_waits_for_undrained_store():
    ops = [Instruction('store', address=128, size=2)] + [Instruction('alu') for _ in range(8)] + [Instruction('load', address=128, size=4)]
    memory = SlowStores()
    c = config(store_policy='buffered', memory_policy='disambiguate', store_drain_width=1)
    result = simulate(ops, c, memory=memory, backend='python')
    assert result['events']['partial_forward_blocked'] > 0
    assert result['events']['stores_drained'] == 1
    writes = [cycle for _,write,cycle in memory.requests if write]
    reads = [cycle for _,write,cycle in memory.requests if not write]
    assert len(writes) == len(reads) == 1
    assert reads[0] >= writes[0] + 12


def test_cache_retry_holds_queue_until_response():
    from rvw.ooo.core import _simulate
    class Miss:
        def __init__(self): self.calls = 0
        def access(self, *args):
            self.calls += 1
            return 15 if self.calls == 1 else 1
    c = config(cache_miss_replay=True, issue_queue_policy='compacting',
               components={'memory': {'l1d': {'size_kib': 16, 'ways': 4, 'latency': 1}}})
    ops = [Instruction('load', dest=1, address=128, size=4)] + [Instruction('alu', sources=(1,), dest=2)]*4
    memory = Miss()
    result = _simulate(ops, c, backend='python', memory=memory)
    assert result['instret'] == len(ops)
    assert result['events']['cache_miss_replays'] == 1
    assert result['events']['issued'] > len(ops)
    assert memory.calls == 2
    assert result['cycles'] >= 15 + c.replay_penalty


def test_retry_window_readmission_respects_issue_capacity():
    from rvw.ooo.core import _simulate
    class Miss:
        def __init__(self): self.calls = 0
        def access(self, *args):
            self.calls += 1
            return 20 if self.calls == 1 else 1
    c = replace(config(cache_miss_replay=True,
               components={'memory': {'l1d': {'size_kib': 16, 'ways': 4, 'latency': 1}}}), issue_entries=2)
    ops = [Instruction('load', dest=1, address=128, size=4)] + [Instruction('alu') for _ in range(10)]
    result = _simulate(ops, c, backend='python', memory=Miss())
    assert result['events']['cache_miss_replays'] == 1
    assert result['events']['replay_readmitted'] > c.issue_entries
    assert result['max_occupancy']['issue_entries'] <= c.issue_entries
    assert result['max_occupancy']['replay_pending'] > c.issue_entries


def test_cache_retry_requires_explicit_cache():
    with pytest.raises(ValueError, match='memory.l1d'):
        config(cache_miss_replay=True)


def test_retry_squashes_wrong_work_before_queue_readmission():
    from rvw.ooo.core import _simulate
    class Miss:
        def __init__(self): self.calls = 0
        def access(self, *args):
            self.calls += 1
            return 20 if self.calls == 1 else 1
    c = replace(config(cache_miss_replay=True, wrong_path_occupancy=True,
                       issue_queue_policy='compacting',
                       components={'memory': {'l1d': {'size_kib': 16, 'ways': 4, 'latency': 1}}}),
                latencies=dict(alu=1, branch=30, load=2, store=2))
    ops = [Instruction('load', address=128, size=4),
           Instruction('branch', pc=4, next_pc=100)] + [Instruction('alu') for _ in range(10)]
    result = _simulate(ops, c, max_cycles=1000, backend='python', memory=Miss())
    assert result['instret'] == len(ops)
    assert result['events']['cache_miss_replays'] == 1
    assert result['events']['wrong_path_squashed'] == result['events']['wrong_path_renamed']
    assert result['max_occupancy']['issue_entries'] <= c.issue_entries


def test_filler_prefix_is_independent_of_rob_capacity():
    from rvw.ooo.speculative import MixWork
    ops = [Instruction('alu'), Instruction('load', address=128, size=4), Instruction('store', address=128, size=4)]
    small = config(wrong_path_occupancy=True)
    large = replace(small, rob_entries=128)
    a, b = MixWork(ops), MixWork(ops)
    for branch in ops:
        # A longer unused capture must not change any later branch's mix.
        x = a.begin(branch, 10, small.rob_entries, small, None)
        y = b.begin(branch, 10, large.rob_entries, large, None)
        assert x == y[:len(x)]


def test_memory_order_window_can_run_without_component_cache():
    c = Config(4,16,4,32,4,8,8,8,4,
               dict(alu=1,divide=12,load=2,store=2),
               memory_policy='speculate', replay_window=True)
    ops = [Instruction('divide',dest=1), Instruction('store',(1,),address=16,size=4),
           Instruction('load',dest=2,address=16,size=4), Instruction('alu',(2,),3)]
    result = simulate(ops,c,backend='python')
    assert result['events']['memory_order_replays'] == 1
    assert result['events']['replay_readmitted'] > 0
    assert result['instret'] == len(ops)


def test_replay_window_flag_is_boolean():
    with pytest.raises(ValueError,match='replay_window'):
        config(replay_window=1)
