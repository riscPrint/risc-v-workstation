"""Large sufficient witnesses and illegal execution controls."""
import time
import pytest
from rvw.memory.axiomatic import search

pytestmark = pytest.mark.fast


def event(i, h, n, kind, address, value):
    return dict(id=i, hart=h, order=n, kind=kind, address=address, size=8,
                addr=[], data=[], ctrl=[], **{'write' if kind == 'W' else 'read': value})


def test_eight_thousand_events_have_sparse_witness():
    events = []
    for h in range(4):
        for n in range(2000):
            events.append(event(f'{h}:{n}', h, n, 'W' if n%2 == 0 else 'R', h*8, n//2))
    start = time.monotonic()
    result = search(events, {(h*8, 8): 0 for h in range(4)})
    assert result['status'] == 'allowed'
    assert result['engine'] == 'sc-witness'
    assert len(result['witness']['global_order']) == 8000
    assert len(result['witness']['co']) == 4000
    assert time.monotonic()-start < 5


def test_large_planted_impossible_read_is_forbidden():
    events = [event(f'w{i}', 0, i, 'W', 0, i) for i in range(2000)]
    events.append(event('bad', 1, 0, 'R', 0, 9999))
    # No read source must be detected before quadratic relation construction.
    result = search(events, {(0, 8): 0})
    assert result['status'] == 'forbidden'


def test_sc_path_validates_dependency_and_sc_identity():
    e = event('r', 0, 0, 'R', 0, 0)
    e['addr'] = ['missing']
    with pytest.raises(ValueError, match='dependency'):
        search([e], {(0, 8): 0})


def test_eight_thousand_shared_amos_have_sparse_witness():
    events = [dict(id=f'{h}:{n}', hart=h, order=n, kind='AMO', address=0, size=8,
                   addr=[], data=[], ctrl=[], read=n*4+h, write=n*4+h+1)
              for h in range(4) for n in range(2000)]
    start = time.monotonic()
    result = search(events, {(0, 8): 0})
    assert result['status'] == 'allowed'
    assert result['engine'] == 'sc-witness'
    assert time.monotonic()-start < 5


def test_incremental_graph_detects_prefix_cycle_without_changing_parent():
    from rvw.memory.search_graph import OrderGraph
    graph = OrderGraph({('a', 'b'), ('b', 'c')})
    child = graph.copy()
    assert not child.add({('c', 'a')})
    assert graph.add({('c', 'd')})
    assert not graph.add({('d', 'a')})


def test_same_value_stores_keep_distinct_read_sources():
    # Two AMOs cannot both read the initial value, even if writes are equal.
    es = [dict(id=str(h), hart=h, order=0, kind='AMO', address=0, size=8,
               addr=[], data=[], ctrl=[], read=0, write=1) for h in range(2)]
    assert search(es, {(0, 8): 0})['status'] == 'forbidden'


def test_record_order_is_not_a_global_order():
    events = [event('r', 1, 1, 'R', 0, 7), event('w', 0, 8, 'W', 0, 7)]
    assert search(events, {(0, 8): 0})['status'] == 'allowed'
    assert search(list(reversed(events)), {(0, 8): 0})['status'] == 'allowed'


def test_sc_scheduler_backtracks_after_conflicting_overwrite():
    events=[event('a',0,0,'W',0,1),event('b',0,1,'R',0,1),
            event('c',1,0,'W',0,2),event('d',1,1,'R',0,2)]
    result=search(events,{(0,8):0})
    assert result['status']=='allowed'
    assert result['engine']=='sc-witness'
    assert result['witness']['global_order']==['a','b','c','d']
    assert result['witness']['scheduling_branches']>1
