"""Reset-domain crossing classes on small exact-schema graphs."""
import pytest
from lint_builder import Builder
from rvw.lint import structural
from rvw.query.db import run_on


pytestmark = pytest.mark.fast


def analyze(db, intent=None):
    return run_on(db, lambda d: structural.analyze(d, intent or {}))


def rules(r):
    return [f['rule'] for f in r['findings']]


def two_resets(tmp_path, src_kind='SYNC', dst_kind='SYNC', dst_init='0', src_init='0'):
    b = Builder(tmp_path / 'd.db')
    b.domain(1, reset='rstA', kind=src_kind)
    b.domain(2, reset='rstB', kind=dst_kind)
    b.sig('clk', direction='in', role='clock')
    b.sig('rstA', direction='in', role='reset')
    b.sig('rstB', direction='in', role='reset')
    b.sig('en', direction='in')
    b.reg('src', 1, init=src_init)
    b.reg('dst', 2, init=dst_init)
    b.edge('src', 'dst')
    return b


@pytest.mark.parametrize('src_kind,dst_init,src_init,expected', [
    ('ASYNC', '0', '0', 'async_assert_crossing'),
    ('SYNC', None, '0', 'resetless_receiver'),
    ('SYNC', '0', '0', 'independent_reset'),
    ('SYNC', '0', None, 'source_not_reset'),
])
def test_crossing_classes(tmp_path, src_kind, dst_init, src_init, expected):
    db = two_resets(tmp_path, src_kind, 'SYNC', dst_init, src_init).done()
    r = analyze(db)
    row = r['rdc']['crossings'][0]
    assert row['class'] == expected
    if expected == 'source_not_reset':
        assert row['status'] == 'no_hazard' and not [x for x in rules(r) if x.startswith('rdc.')]
    else:
        assert 'rdc.' + expected in rules(r)
        assert r['rdc']['status'] == 'findings'
    assert r['status'] == 'inconclusive'


def test_declared_isolation_protects_and_unmatched_is_error(tmp_path):
    b = two_resets(tmp_path)
    b.edge('en', 'dst', 'cond')
    db = b.done()
    good = dict(destination='dst', qualifier='en', reason='dst samples only when en is set after reset')
    r = analyze(db, {'isolation': [good]})
    assert r['rdc']['crossings'][0]['status'] == 'protected'
    assert r['rdc']['status'] == 'protected'
    assert not [x for x in rules(r) if x.startswith('rdc.')]
    bad = dict(good, qualifier='rstA')
    r = analyze(db, {'isolation': [bad]})
    assert 'rdc.isolation_unmatched' in rules(r) and 'rdc.independent_reset' in rules(r)
    with pytest.raises(ValueError, match='isolation'):
        analyze(db, {'isolation': [dict(good, reason=' ')]})
    with pytest.raises(ValueError, match='unknown signal'):
        analyze(db, {'isolation': [dict(good, qualifier='nothing')]})


def reset_sync(tmp_path, broken=None):
    b = Builder(tmp_path / 'd.db')
    b.domain(1, reset='rawReset', kind='ASYNC')          # synchronizer stages
    b.domain(2, reset='syncReset', kind='ASYNC')         # users
    b.sig('clk', direction='in', role='clock')
    b.sig('rawReset', direction='in', role='reset')
    b.component('sync', 'spinal.lib.BufferCC')
    b.sig('sync.dataIn', direction='in', comp='sync')    # constant input: no edges
    b.reg('sync.s0', 1, comp='sync')
    b.reg('sync.s1', 1, comp='sync')
    b.sig('syncReset', role='reset')
    b.chain('sync.dataIn', 'sync.s0', 'sync.s1', 'syncReset')
    b.reg('user', 2)
    b.sig('din', direction='in')
    b.edge('din', 'user')
    if broken == 'single':
        b.c.execute("DELETE FROM edges WHERE src=? AND dst=?", (b.ids['sync.s0'], b.ids['sync.s1']))
        b.edge('sync.dataIn', 'sync.s1')
    if broken == 'logic':
        b.sig('other', direction='in')
        b.edge('other', 'syncReset')
    if broken == 'data':
        b.edge('syncReset', 'user')
    return b.done()


@pytest.mark.parametrize('broken', [None, 'single', 'logic', 'data'])
def test_reset_synchronizer_recognition(tmp_path, broken):
    r = analyze(reset_sync(tmp_path, broken))
    users = next(d for d in r['rdc']['domains'] if d['reset'] == 'syncReset')
    assert users['release'] == ('unsynchronized' if broken in ('single', 'logic') else 'synchronized')
    if broken is None:
        assert users['synchronizers'][0]['stages'] == ['sync.s0', 'sync.s1']
    found = set(rules(r))
    assert ('rdc.comb_reset_logic' in found) == (broken == 'logic')
    assert ('rdc.reset_as_data' in found) == (broken == 'data')
    raw = next(d for d in r['rdc']['domains'] if d['reset'] == 'rawReset')
    if broken in ('single', 'logic'):
        assert 'rdc.async_release_unsynchronized' in found
    else:
        assert raw['release'] == 'synchronizer_stages'
        assert 'rdc.async_release_unsynchronized' not in found


def test_missing_domain_is_inconclusive(tmp_path):
    b = two_resets(tmp_path)
    b.c.execute("UPDATE signals SET clock_domain_id=9 WHERE path='dst'")
    r = analyze(b.done())
    assert r['rdc']['status'] == 'inconclusive'
    assert 'rdc.missing_domain' in rules(r)
    assert r['rdc']['crossings'][0]['status'] == 'inconclusive'


def test_reconvergence_respects_declared_protection(tmp_path):
    b = two_resets(tmp_path)
    b.reg('local', 2)
    b.edge('local', 'dst')
    b.edge('en', 'dst', 'cond')
    db = b.done()
    assert 'rdc.reconvergence' in rules(analyze(db))
    r = analyze(db, {'isolation': [dict(destination='dst', qualifier='en', reason='gated after reset')]})
    assert 'rdc.reconvergence' not in rules(r)
    assert r['rdc']['protected_merges'] == ['dst']
