from copy import deepcopy

import pytest

from rvw.debug.parity import compare


def graph():
    return {'vertices': [{'file': 'Old.scala', 'line': 12, 'name': 'Old.scala:12', 'timestamp': 1},
                         {'file': 'Design.scala', 'line': 7, 'name': 'real', 'timestamp': 1}],
            'edges': [{'from': 0, 'to': 1, 'kind': 'data'}, {'from': 0, 'to': 1, 'kind': 'data'}]}


def test_caller_equivalence_is_explicit_and_preserves_source_and_edges():
    old = graph()
    new = deepcopy(old)
    new['vertices'][0].update(file='New.scala', line=30, name='New.scala:30')
    kw = dict(kind='trace', callers=[('Old.scala', 12, 'New.scala', 30)])
    assert not compare(old, new, kind='trace')
    assert compare(old, new, **kw)
    assert old == graph()
    for field, value in [('line', 8), ('timestamp', 2), ('name', 'changed')]:
        bad = deepcopy(new)
        bad['vertices'][1][field] = value
        assert not compare(old, bad, **kw)
    bad = deepcopy(new)
    bad['edges'].pop()
    assert not compare(old, bad, **kw)
    bad = deepcopy(new)
    bad['edges'][0]['kind'] = 'control'
    assert not compare(old, bad, **kw)


def test_blocks_caller_ids_and_references_change_together():
    old = {'generated': 1, 'nodes': [{'id': 'sig:Old_l12', 'name': 'Old_l12', 'loc': {'file': 'Old.scala', 'line': 12}}], 'refs': [{'id': 'sig:Old_l12'}]}
    new = {'generated': 2, 'nodes': [{'id': 'sig:New_l30', 'name': 'New_l30', 'loc': {'file': 'New.scala', 'line': 30}}], 'refs': [{'id': 'sig:New_l30'}]}
    kw = dict(kind='blocks', callers=[('Old.scala', 12, 'New.scala', 30)])
    assert compare(old, new, **kw)
    new['refs'][0]['id'] = 'sig:New_l31'
    assert not compare(old, new, **kw)


def test_source_roots_do_not_drop_file_identity():
    a = {'file': '/old/src/pkg/A.scala', 'line': 1}
    b = {'file': '/new/src/pkg/A.scala', 'line': 1}
    assert compare(a, b, kind='blocks', left_roots=['/old'], right_roots=['/new'])
    b['file'] = '/new/src/other/A.scala'
    assert not compare(a, b, kind='blocks', left_roots=['/old'], right_roots=['/new'])
    with pytest.raises(ValueError, match='empty graph'):
        compare({'vertices': [], 'edges': []}, {'vertices': [], 'edges': []}, kind='trace')


def test_duplicate_labels_need_identity_mapping():
    g = graph()
    g['vertices'][1] = dict(g['vertices'][0])
    with pytest.raises(ValueError, match='duplicate vertex'):
        compare(g, g, kind='trace')
