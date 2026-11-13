import json
import pytest
from rvw.cli import main
from rvw.query.db import DesignDB, QueryError
from rvw.query import semantic

pytestmark = pytest.mark.fast


def test_semantic_queries(cluster_db):
    db = DesignDB(cluster_db)
    try:
        d = semantic.definition(db, 'fifo.logic_ptr_push')
        assert d['signal']['path'] == 'fifo.logic_ptr_push'
        assert d['status'] == 'mapped'
        refs = semantic.references(db, 'fifo.logic_ptr_push')
        assert refs['reader_count'] > 0 and refs['assignments']
        p = semantic.parameters(db, 'fifo')
        assert p['status'] == 'unavailable' and p['parameters'] is None
        m = semantic.explain_module(db, 'fifo')
        assert m['schema'] == 'rvw.module-explanation/1' and m['ports']
        assert m['registers'] and m['clock_domains']
        t = semantic.expression_type(db, 'fifo.logic_ptr_push')
        assert t['width'] == 3
        assert semantic.expression_type(db, 'fifo.logic_ptr_push[1:0]')['width'] == 2
        with pytest.raises(QueryError):
            semantic.expression_type(db, 'fifo.logic_ptr_push + 1')
        with pytest.raises(QueryError):
            semantic.expression_type(db, 'fifo.logic_ptr_push[99:0]')
        diff = semantic.hierarchy_diff(db, db)
        assert not diff['added'] and not diff['changed'] and not diff['removed']
    finally:
        db.close()


def test_cli_and_mcp(cluster_db, capsys):
    from rvw.query.commands.semantic import mcp_tools
    assert main(['query', 'explain-module', 'fifo', '--db', str(cluster_db), '--json']) == 0
    out = json.loads(capsys.readouterr().out)
    spec = next(s for s in mcp_tools() if s.name == 'query_explain_module')
    assert spec.handler(db=str(cluster_db), path='fifo')['counts'] == out['counts']
    assert main(['query', 'hierarchy-diff', str(cluster_db), str(cluster_db), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['changed'] == []


def test_changed_hierarchy_and_port_bindings(cluster_db, tmp_path):
    import sqlite3
    import shutil
    from rvw.query.commands.semantic import compare
    other = tmp_path / 'other.db'
    shutil.copyfile(cluster_db, other)
    with sqlite3.connect(other) as c:
        c.execute("UPDATE components SET module='Changed' WHERE path='fifo'")
        value = json.dumps({'fifo': [{'name': 'en', 'status': 'tied', 'bits_lsb_first': ['0']}] }).encode()
        c.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)',
                  ('hdl/port-connections.json', 'application/json', 'identity', len(value), value))
    assert compare(str(cluster_db), str(other))['changed'][0]['path'] == 'fifo'
    db = DesignDB(other)
    try:
        assert semantic.port_status(db, 'fifo')['ports'][0]['status'] == 'tied'
    finally:
        db.close()
