"""Preserve native empty and omitted instance connections for agent queries."""
import json
import sqlite3
import pytest
from rvw.query.hdl import _Writer, _artifact, schema_sql
from rvw.query.db import DesignDB
from rvw.query.semantic import port_status

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('explicit_empty', [True, False])
def test_open_and_tied_port_bindings(tmp_path, explicit_empty):
    ports = {'a': {'direction': 'input', 'bits': [2]},
             'y': {'direction': 'output', 'bits': [3, 4, 5, 6]}}
    connections = {'a': ['0']}
    if explicit_empty:
        connections['y'] = []
    modules = {
        'top': {'ports': {}, 'netnames': {}, 'cells': {'u': {'type': 'leaf', 'connections': connections}}},
        'leaf': {'ports': ports, 'netnames': {n: {'bits': p['bits'], 'hide_name': 0} for n, p in ports.items()}, 'cells': {}},
    }
    out = tmp_path / 'ports.db'
    with sqlite3.connect(out) as c:
        c.executescript(schema_sql())
        writer = _Writer(c, {'modules': modules}, {})
        writer.instance('top', '', None)
        writer.domains()
        _artifact(c, 'hdl/port-connections.json', writer.port_connections)
        c.executemany('INSERT INTO meta VALUES (?,?)', [('schema', 'rvw.designdb/20'),
                      ('toplevel', 'top'), ('frontend', 'yosys-verilog'),
                      ('hdl_port_connection_coverage', 'all-instance-ports')])
    db = DesignDB(out)
    try:
        status = port_status(db, 'u')
        assert status['coverage'] == 'all-instance-ports'
        result = {p['name']: p for p in status['ports']}
        assert result['a']['status'] == 'tied' and result['a']['bits_lsb_first'] == ['0']
        assert result['y']['status'] == 'unconnected' and result['y']['width'] == 4
        assert result['y']['bits_lsb_first'] == []
    finally:
        db.close()
