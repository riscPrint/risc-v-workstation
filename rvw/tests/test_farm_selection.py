import hashlib
import sqlite3
from rvw.farm.selection import select


import pytest

pytestmark = pytest.mark.fast


def inputs(tmp_path):
    db = tmp_path / 'design.sqlite'
    with sqlite3.connect(db) as c:
        c.executescript('CREATE TABLE files(id,path); CREATE TABLE components(id,file_id); CREATE TABLE signals(id,path,component_id,file_id); CREATE TABLE edges(src,dst);')
        c.execute("INSERT INTO files VALUES(1,'Unit.scala')")
        c.execute('INSERT INTO components VALUES(1,1)')
        c.execute("INSERT INTO signals VALUES(1,'unit.a',1,1)")
        c.execute("INSERT INTO signals VALUES(2,'output.b',2,2)")
        c.execute('INSERT INTO edges VALUES(1,2)')
    catalogue = dict(database_sha256=hashlib.sha256(db.read_bytes()).hexdigest(), tests=[
        dict(id='fast', signals=['unit.a', 'output.b'], wall_seconds=2),
        dict(id='slow', signals=['unit.a'], wall_seconds=10),
        dict(id='mandatory', signals=[], wall_seconds=1, mandatory=True)])
    return db, catalogue


def test_transitive_impact_and_time_budget(tmp_path):
    db, catalogue = inputs(tmp_path)
    result = select(db, ['Unit.scala'], catalogue, 3)
    assert [s['id'] for s in result['selected']] == ['mandatory', 'fast']
    assert result['affected_signals'] == ['output.b', 'unit.a']
    assert result['uncovered'] == []
    assert result['advisory'] and not result['gate_acceptance']


def test_stale_and_unknown_never_drop_tests(tmp_path):
    db, catalogue = inputs(tmp_path)
    catalogue['database_sha256'] = 'stale'
    result = select(db, ['new.scala'], catalogue, 1)
    assert len(result['selected']) == 3
    assert result['over_budget']
    assert result['unknown_sources'] == ['new.scala']


def test_existing_coverage_fallback_is_preserved(tmp_path):
    db, catalogue = inputs(tmp_path)
    catalogue['coverage_selection'] = dict(fallback_all=True)
    assert len(select(db, ['Unit.scala'], catalogue, 3)['selected']) == 3
