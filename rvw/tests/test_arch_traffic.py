from rvw.arch.traffic import model


import pytest

pytestmark = pytest.mark.fast


def plan(capacity=4):
    return dict(schema='rvw.traffic-plan/1', resources={'memory': dict(bytes_per_cycle=8, latency=10, capacity=capacity)},
                agents={'cpu': dict(route=['memory'], requests=[dict(cycle=0, bytes=64), dict(cycle=0, bytes=64)])})


def test_bandwidth_latency_and_queue_capacity():
    r = model(plan())
    assert [row['finish'] for row in r['requests']] == [18, 26]
    assert r['resources']['memory']['peak'] == 2
    assert r['resources']['memory']['energy_j'] is None
    r = model(plan(1))
    assert [row['finish'] for row in r['requests']] == [18, 36]
    assert r['resources']['memory']['queue_full'] == 1
    assert r['resources']['memory']['queue_wait_cycles'] == 18


def test_interference_and_multihop():
    p = plan()
    p['resources']['bus'] = dict(bytes_per_cycle=16, latency=2, capacity=4)
    p['agents']['dma'] = dict(route=['bus', 'memory'], requests=[dict(cycle=0, bytes=128)])
    r = model(p)
    assert r['agents']['dma']['requests'] == 1
    assert r['resources']['memory']['bytes'] == 256
    assert r['agents']['cpu']['mean_latency'] == 22
    assert r['requests'][-1]['finish'] == 42


def test_abstract_sleep_and_wake_costs():
    p = plan()
    p['clock_hz'] = 1000
    p['agents']['cpu']['requests'] = [dict(cycle=100, bytes=8)]
    p['resources']['memory']['power'] = dict(active_w=2, idle_w=1, sleep_w=0,
        sleep_after=10, wake_cycles=5, wake_j=0.01, source='project hypothetical model')
    r = model(p)
    m = r['resources']['memory']
    assert m['wakes'] == 1
    assert r['cycles'] == 116
    assert m['active_cycles'] == 11
    assert m['energy_j'] > 0
