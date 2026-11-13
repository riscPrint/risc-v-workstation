from rvw.formal.deep_model import abstract, induction, mine
from rvw.formal.deep_grid import grid


def model():
    return {'states': {'a': {'x': 0, 'ram0': 0}, 'b': {'x': 0, 'ram0': 1},
                       'c': {'x': 1, 'ram0': 1}},
            'initial': ['a'], 'edges': [['a', 'a'], ['b', 'c'], ['c', 'c']],
            'properties': {'safe': ['c']}}


def test_spurious_needs_refinement():
    m = model()
    r = abstract(m, 'safe', ['x'], 0)
    assert r['status'] == 'inconclusive' and r['reason'] == 'spurious'
    r = abstract(m, 'safe', ['x'])
    assert r['status'] == 'pass'
    assert r['rounds'][0]['refine'] == 'ram0'


def test_replays_concrete_failure():
    m = model()
    m['edges'].append(['a', 'b'])
    r = abstract(m, 'safe')
    assert r['status'] == 'fail'
    assert r['trace'] == ['a', 'b', 'c']


def test_induction_helpers_and_rejected_samples():
    m = model()
    assert induction(m, 'safe', 1)['status'] == 'inconclusive'
    r = induction(m, 'safe', samples=[m['states']['a']])
    assert r['status'] == 'pass'
    assert any(h['expression'] == '0 <= ram0 <= 0' and h['status'] == 'proven' for h in r['helpers'])
    m['edges'].append(['a', 'b'])
    assert all(h['status'] == 'rejected' for h in mine(m, [m['states']['a']]))
    assert induction(m, 'safe', samples=[m['states']['a']])['status'] == 'fail'


def test_relational_mining():
    m = {'states': {'a': {'x': 0, 'y': 0}, 'b': {'x': 1, 'y': 1}},
         'initial': ['a'], 'edges': [['a', 'b'], ['b', 'a']], 'properties': {'safe': []}}
    assert any(h['expression'] == 'x - y == 0' and h['status'] == 'proven' for h in mine(m, list(m['states'].values())))


def test_grid(tmp_path):
    m = model()
    m['properties']['broken'] = ['a']
    r = grid(m, tmp_path / 'out', workers=2)
    assert r['status'] == 'fail'
    assert {x['property']: x['status'] for x in r['rows']} == {'safe': 'pass', 'broken': 'fail'}
