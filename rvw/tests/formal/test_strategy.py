import pytest
from rvw.formal.strategy import select

pytestmark = pytest.mark.fast


def model(*kinds):
    return {'modules': {'t': {'cells': {str(i): {'type': k, 'connections': {'Q': list(range(32))}} for i,k in enumerate(kinds)}}}}


def test_boolean_and_memory_order_and_candidates():
    assert select(model('$dff'))['engines'][0]=='abc:pdr'
    r=select(model('$mem_v2','$mul','$add',*(['$dff']*9)))
    assert r['engines'][0]=='smtbmc:yices'
    assert r['abstractions']==['lazy-ram','uf-prove','counter-quotient_requires_leaf_binding','rtl-refine']
    assert r['features']['state_bits']==288


def test_only_qualified_history_changes_order():
    history={'rows':[{'engine':'aiger:rIC3','problem_status':'pass','total_wall_s':1},
                     {'engine':'smtbmc:yices','problem_status':'inconclusive','status':'pass','total_wall_s':.1},
                     {'engine':'smtbmc:bitwuzla','problem_status':'bounded_pass','total_wall_s':.1}]}
    r=select(model('$dff'),[history])
    assert r['engines'][0]=='aiger:rIC3'
    assert list(r['history_samples'])==['aiger:rIC3']


def test_liveness_needs_reduction():
    r=select(model('$live'))
    assert not r['engines'] and r['abstractions']==['liveness-to-safety','k-live']
