"""HDL packed nets are endpoint views, not cross-lane dependency nodes."""
import sqlite3
import pytest
from rvw.query.hdl import _Writer, schema_sql
from rvw.query.db import DesignDB
from rvw.query import ops

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('hidden', [False, True])
def test_packed_alias_is_not_a_cross_lane_path(tmp_path, hidden):
    ports = {'a': {'direction': 'input', 'bits': [2]}, 'b': {'direction': 'input', 'bits': [3]},
             'x': {'direction': 'output', 'bits': [2]}, 'y': {'direction': 'output', 'bits': [3]}}
    netnames = {n: {'bits': v['bits'], 'hide_name': 0} for n, v in ports.items()}
    netnames['pair'] = {'bits': [2, 3], 'hide_name': int(hidden)}
    out = tmp_path / 'alias.db'
    with sqlite3.connect(out) as conn:
        conn.executescript(schema_sql())
        writer = _Writer(conn, {'modules': {'top': {'ports': ports, 'netnames': netnames, 'cells': {}}}}, {})
        writer.instance('top', '', None)
        writer.domains()
        conn.executemany('INSERT INTO meta VALUES (?,?)', [('schema', 'rvw.designdb/20'),
                         ('toplevel', 'top'), ('frontend', 'yosys-verilog')])
    db = DesignDB(out)
    try:
        assert ops.path(db, 'a', 'x')['found']
        assert ops.path(db, 'b', 'y')['found']
        assert not ops.path(db, 'a', 'y')['found']
        assert not ops.path(db, 'b', 'x')['found']
        assert ops.path(db, 'pair', 'x')['found'] and ops.path(db, 'pair', 'y')['found']
        assert ops.path(db, 'a', 'pair')['found'] and ops.path(db, 'b', 'pair')['found']
        assert 'y' not in {n['path'] for n in ops.fanout(db, 'a', depth=8)['nodes']}
        assert 'a' not in {n['path'] for n in ops.fanin(db, 'y', depth=8)['nodes']}
    finally:
        db.close()
