from rvw.ooo.component_events import counters


def test_only_observed_counts_are_exposed():
    stats = {'memory': {'l1d': {'demand_accesses':10,'demand_misses':2,'miss_rate':0.2},
                       'tlb': {'walks':1,'l1':{'accesses':10,'misses':1}}}}
    events = counters(stats)
    assert events == {'l1d_demand_accesses':10,'l1d_demand_misses':2,
                      'tlb_walks':1,'tlb_l1_accesses':10,'tlb_l1_misses':1}
    assert 'l2_demand_misses' not in events
