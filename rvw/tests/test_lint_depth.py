"""Small exact-schema reference graphs. These are not extracted RTL evidence."""
import sqlite3
import pytest
from test_lint import fixture_db, settings
from rvw.lint import structural
from rvw.lint.cli import report
from rvw.query.db import run_on


def add_reg(c, i, domain, width=1):
    c.execute('INSERT INTO signals(id,component_id,name,path,kind,width,clock_domain_id,file_id,line) VALUES(?,1,?,?,\'reg\',?,?,1,?)',
              (i, f'r{i}', f'r{i}', width, domain, i))


def edges(c, pairs):
    for a, b in pairs:
        c.execute("INSERT INTO edges VALUES(?,?,'data')", (a, b))


def result(db, intent=None):
    return run_on(db, lambda d: structural.analyze(d, intent))


def rules(r):
    return {f['rule'] for f in r['findings']}


@pytest.mark.parametrize('fault', ['none', 'fanout', 'logic', 'wrong_clock', 'width'])
def test_two_ff_reference(tmp_path, fault):
    db = fixture_db(tmp_path, 'sync')
    with sqlite3.connect(db) as c:
        if fault == 'fanout':
            add_reg(c, 4, 2); edges(c, [(2, 4)])
        if fault == 'logic':
            add_reg(c, 4, 2)
            c.execute("UPDATE signals SET kind='wire' WHERE id=4")
            c.execute('DELETE FROM edges WHERE src=2 AND dst=3')
            edges(c, [(2,4),(4,3)])
        if fault == 'wrong_clock':
            c.execute('UPDATE signals SET clock_domain_id=1 WHERE id=3')
        if fault == 'width':
            c.execute('UPDATE signals SET width=8 WHERE id=3')
    assert bool(result(db)['depth']['structures']) == (fault == 'none')


def protocol_reference(tmp_path, fifo=False, fault=False):
    db = fixture_db(tmp_path, 'sync', width=3 if fifo else 1)
    with sqlite3.connect(db) as c:
        for i, domain in [(4,2),(5,1),(6,1)]:
            add_reg(c, i, domain, 3 if fifo else 1)
        edges(c, [(4,5),(5,6)])
        if fault:
            edges(c, [(1,5)])
        if fifo:
            c.execute("INSERT INTO signals(id,component_id,name,path,kind,width) VALUES(7,1,'fifo','fifo','mem',8)")
            for target, binary in [(1,'writeBinary'), (4,'readBinary')]:
                key = f' := CastUIntToBits[3](Operator$UInt$Xor[3]({binary}:UInt[3],Operator$UInt$ShiftRightByIntFixedWidth<1>[3]({binary}:UInt[3])))'
                c.execute("INSERT INTO assignments(id,target_id,component_id,kind,key,seq) VALUES(?,?,1,'data',?,0)", (target,target,key))
            c.execute("INSERT INTO memories(id,signal_id,component_id,name,path,width,depth) VALUES(1,7,1,'fifo','fifo',8,4)")
            c.execute("INSERT INTO mem_ports(id,memory_id,kind,clock_domain_id) VALUES(1,1,'write',1)")
            c.execute("INSERT INTO mem_ports(id,memory_id,kind,clock_domain_id) VALUES(2,1,'read_sync',2)")
    p = dict(kind='async_fifo' if fifo else 'handshake', forward=['r1','r2','r3'], reverse=['r4','r5','r6'])
    if fifo:
        p.update(memory='fifo', encoding='gray')
    return db, {'protocols': [p]}


@pytest.mark.parametrize('fifo', [False, True])
@pytest.mark.parametrize('fault', [False, True])
def test_bidirectional_protocol_reference(tmp_path, fifo, fault):
    db, intent = protocol_reference(tmp_path, fifo, fault)
    r = result(db, intent)
    kind = 'async_fifo' if fifo else 'handshake'
    assert f'cdc.{kind}_' + ('invalid' if fault else 'candidate') in rules(r)
    assert r['status'] == 'inconclusive'
    assert 'cdc.protocol' in {x['id'] for x in r['rules']}
    if fifo:
        assert all(r['depth']['structures'][-1]['encoding_evidence'])


@pytest.mark.parametrize('fault', ['read_domain', 'depth', 'width', 'missing_memory'])
def test_fifo_rejects_topology_fault(tmp_path, fault):
    db, intent = protocol_reference(tmp_path, True)
    with sqlite3.connect(db) as c:
        if fault == 'read_domain':
            c.execute("UPDATE mem_ports SET clock_domain_id=1 WHERE kind='read_sync'")
        elif fault == 'depth':
            c.execute('UPDATE memories SET depth=3')
        elif fault == 'width':
            c.execute('UPDATE signals SET width=4 WHERE id=4')
        else:
            intent['protocols'][0]['memory'] = 'missing'
    assert 'cdc.async_fifo_invalid' in rules(result(db, intent))


@pytest.mark.parametrize('merge', [False, True])
def test_reconvergence_reference(tmp_path, merge):
    db = fixture_db(tmp_path, 'sync')
    with sqlite3.connect(db) as c:
        for i, d in [(4,1),(5,2),(6,2),(7,2)]:
            add_reg(c, i, d)
        edges(c, [(4,5),(5,6),(3,7)])
        if merge:
            # A wire between the second stage and the sink exercises cone traversal.
            add_reg(c, 8, 2)
            c.execute("UPDATE signals SET kind='wire' WHERE id=8")
            edges(c, [(6,8),(8,7)])
    assert ('cdc.reconvergence' in rules(result(db))) == merge


@pytest.mark.parametrize('ordered', [False, True])
def test_reset_order_reference(tmp_path, ordered):
    db = fixture_db(tmp_path)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE clock_domains SET reset_kind='SYNC',reset_key='resetA',reset='resetA' WHERE id=1")
        c.execute("UPDATE clock_domains SET reset_kind='SYNC',reset_key='resetB',reset='resetB' WHERE id=2")
    r = result(db, {'reset_order': [['resetA','resetB']] if ordered else []})
    assert ('rdc.release_order_unproved' in rules(r)) != ordered
    assert [x['status'] for x in r['depth']['reset_ordering']] == ([] if ordered else ['unproved'])
    assert r['rdc']['crossings'][0]['status'] == ('protected' if ordered else 'finding')
    assert r['rdc']['status'] == ('protected' if ordered else 'findings')
    assert 'rdc.release' in {x['id'] for x in r['rules']}
    with pytest.raises(ValueError, match='cycle'):
        result(db, {'reset_order': [['resetA','resetB'],['resetB','resetA']]})
    with pytest.raises(ValueError, match='unknown'):
        result(db, {'reset_order': [['resetA','typo']]})


@pytest.mark.parametrize('independent', [False, True])
def test_reset_reconvergence_reference(tmp_path, independent):
    db = fixture_db(tmp_path, 'same')
    with sqlite3.connect(db) as c:
        c.execute("UPDATE clock_domains SET clock_key='clk',reset_kind='SYNC',reset_key='resetA'")
        if independent:
            c.execute("UPDATE clock_domains SET reset_key='resetB' WHERE id=2")
            c.execute('UPDATE signals SET clock_domain_id=2 WHERE id=3')
        edges(c, [(3,2)])
    assert ('rdc.reconvergence' in rules(result(db))) == independent


def test_intent_is_part_of_waiver_identity(tmp_path):
    import json
    db, intent = protocol_reference(tmp_path)
    p = settings(tmp_path, db)
    cfg = json.loads(p.read_text()); cfg['intent'] = intent
    p.write_text(json.dumps(cfg))
    first = next(f for f in report(p)['backends']['structural']['findings'] if f['rule'] == 'cdc.handshake_candidate')
    cfg['waivers'] = [dict(rule=first['rule'], endpoint=first['endpoint'], finding_id=first['id'], config='reference', reason='Reference only.')]
    cfg['intent']['protocols'][0]['reverse'] = ['r4','r6','r5']
    p.write_text(json.dumps(cfg))
    r = report(p)
    assert r['waivers'][0]['matches'] == 0
    assert 'cdc.handshake_invalid' in rules(r['backends']['structural'])


@pytest.mark.parametrize('intent', [{'extra': []}, {'protocols': [None]}, {'reset_order': ['bad']}])
def test_invalid_intent(tmp_path, intent):
    with pytest.raises(ValueError):
        result(fixture_db(tmp_path), intent)


@pytest.mark.parametrize('fault', ['missing', 'wrong_shift', 'conditional', 'multiple'])
def test_fifo_rejects_unestablished_gray(tmp_path, fault):
    db, intent = protocol_reference(tmp_path, True)
    with sqlite3.connect(db) as c:
        if fault == 'missing':
            c.execute('DELETE FROM assignments WHERE target_id=1')
        elif fault == 'wrong_shift':
            c.execute("UPDATE assignments SET key=replace(key,'<1>','<2>') WHERE target_id=1")
        elif fault == 'conditional':
            c.execute('UPDATE assignments SET cond_id=1 WHERE target_id=1')
        else:
            c.execute("INSERT INTO assignments(id,target_id,component_id,kind,key,seq) VALUES(20,1,1,'data','other',1)")
    assert 'cdc.async_fifo_invalid' in rules(result(db, intent))


def test_sequential_reconvergence_depth(tmp_path):
    db = fixture_db(tmp_path, 'sync')
    with sqlite3.connect(db) as c:
        for i, d in [(4,1),(5,2),(6,2),(7,2),(8,2),(9,2)]:
            add_reg(c, i, d)
        edges(c, [(4,5),(5,6),(3,7),(6,8),(7,9),(8,9)])
    assert 'cdc.reconvergence' not in rules(result(db))
    r = result(db, {'reconvergence_depth': 2})
    finding = next(f for f in r['findings'] if f['rule'] == 'cdc.reconvergence')
    assert finding['endpoint'] == 'r9'
    assert finding['reconvergence'] == [dict(endpoint='r3', register_depth=2),
                                        dict(endpoint='r6', register_depth=2)]
    assert r['depth']['reconvergence_depth'] == 2


@pytest.mark.parametrize('value', [0, 65, True, '2'])
def test_invalid_reconvergence_depth(tmp_path, value):
    with pytest.raises(ValueError, match='reconvergence_depth'):
        result(fixture_db(tmp_path), {'reconvergence_depth': value})
