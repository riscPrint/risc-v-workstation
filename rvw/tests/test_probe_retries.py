import pytest
from rvw.probes.events import Probe, Stream, parse_probe
from rvw.probes.retries import retry_statistics

pytestmark = pytest.mark.fast


def stream(rows):
    return Stream({}, [Probe(0,'stage','rename',[('id',4)],dict(first='true',stage='Rn')),
                       Probe(1,'lsuretry','cache',[('id',4)],dict(cause='cache_miss_retry')),
                       Probe(2,'stage','complete',[('id',4)],dict(stage='Wb')),
                       Probe(3,'retire','commit',[('id',4)]),
                       Probe(4,'flush','tail',[('id',4),('inclusive',1)],dict(range='younger'))], rows, dict(end=True))


def test_typed_declaration():
    p = dict(id=0,kind='lsuretry',name='cache',fields=[['id',4]],meta=dict(cause='cache_miss_retry'))
    assert parse_probe(p).kind == 'lsuretry'
    with pytest.raises(ValueError, match='cause'):
        parse_probe(dict(p,meta=dict(cause='branch')))
    with pytest.raises(ValueError, match='instruction id'):
        parse_probe(dict(p,fields=[]))


def test_completion_and_reused_id():
    s=stream([(0,0,[1]),(2,1,[1]),(6,2,[1]),(7,3,[1]),(8,0,[1]),(9,1,[1]),(10,4,[1,1])])
    r=retry_statistics(s)
    assert not r['findings']
    c=r['causes']['cache_miss_retry']
    assert c['retry_to_completion_cycles'] == [4]
    assert c['counts'] == dict(attempts=2,linked=2,flushed=1)


def test_orphan_and_repeated_attempts():
    s=stream([(0,1,[2]),(1,0,[1]),(2,1,[1]),(3,1,[1]),(8,2,[1])])
    r=retry_statistics(s)
    assert r['status']=='violations'
    c=r['causes']['cache_miss_retry']
    assert c['counts']['rejected_again']==1
    assert c['retry_to_completion_cycles']==[5]


def test_zero_activation_is_explicit():
    r=retry_statistics(stream([(0,0,[1]),(1,3,[1])]))
    assert r['causes']['cache_miss_retry']['retry_to_completion_cycles']==[]
    assert not r['causes']['cache_miss_retry']['counts']


def test_order_violation_does_not_time_stale_completion():
    s=stream([(0,0,[1]),(2,1,[1]),(3,2,[1]),(4,4,[1,1])])
    s.probes[1].meta['cause']='memory_order_violation'
    r=retry_statistics(s)['causes']['memory_order_violation']
    assert r['retry_to_completion_cycles']==[]
    assert r['counts']['flushed']==1


def test_distinct_cause_supersedes_wait_without_counting_same_retry():
    s=stream([(0,0,[1]),(1,1,[1]),(2,5,[1]),(3,2,[1])])
    s.probes.append(Probe(5,'lsuretry','forward',[('id',4)],dict(cause='store_forward_miss')))
    r=retry_statistics(s)['causes']
    assert r['cache_miss_retry']['counts']['superseded']==1
    assert 'rejected_again' not in r['cache_miss_retry']['counts']
    assert r['store_forward_miss']['retry_to_completion_cycles']==[1]
