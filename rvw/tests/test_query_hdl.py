"""Native HDL translation tests. Yosys is the independent connectivity oracle."""
import json
from pathlib import Path
import re
import shutil

import pytest

from rvw.cli import main
from rvw.query import ops
from rvw.query.db import DesignDB
from rvw.query.hdl import build_hdl

YOSYS = shutil.which('yosys')

SV = '''module leaf(input logic clk, a, b, sel, output logic q);
logic d;
assign d = sel ? a : b;
always_ff @(posedge clk) q <= d;
endmodule
module top(input logic clk, a, b, sel, output logic q, r);
leaf u0(clk,a,b,sel,q);
leaf u1(clk,b,a,sel,r);
endmodule
'''


def test_schema_matches_scala():
    from rvw.query.hdl import schema_sql
    scala = (Path(__file__).parents[2] / 'SpinalDB/spinaldb/src/main/scala/spinaldb/Schema.scala').read_text()
    expected = []
    for match in re.finditer(r'"""(.*?)"""\.stripMargin|"(CREATE [^"\n]+)"', scala, re.S):
        expected.append(re.sub(r'\n\s*\|', '\n', match[1]) if match[1] else match[2])
    assert [' '.join(x.split()) for x in schema_sql().split(';') if x.strip()] == [
        ' '.join(x.split()) for x in expected]


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
def test_hierarchy_queries(tmp_path, capsys):
    source = tmp_path / 'design.sv'
    source.write_text(SV)
    out = tmp_path / 'design.db'
    build_hdl([source], 'top', out, yosys=YOSYS)
    db = DesignDB(out)
    try:
        assert len(ops.hierarchy(db)['root']['children']) == 2
        assert ops.path(db, 'a', 'q')['found']
        assert ops.path(db, 'sel', 'q')['found']
        assert not ops.path(db, 'q', 'a')['found']
        assert ops.drivers(db, 'u0.d')['assignments']
        assert ops.loads(db, 'a')['readers']
        assert ops.where(db, 'a')['signal']['loc'] == f'{source}:6'
        assert db.resolve_one('u0.q').kind == 'reg'
        assert db.meta['frontend'] == 'yosys-verilog'
    finally:
        db.close()
    for command in [('drivers', 'u0.d'), ('loads', 'a'), ('path', 'a', 'q')]:
        assert main(['query', *command, '--db', str(out), '--json']) == 0
        assert 'error' not in json.loads(capsys.readouterr().out)


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
@pytest.mark.parametrize('body', [
    'module top(inout a); endmodule',
    'module top(input a, output b); missing u(a,b); endmodule',
    '`include "missing.sv"\nmodule top; endmodule',
    'module top(input [3:0] a, input clk, output reg [3:0] q); reg [3:0] m[0:7]; always @(posedge clk) begin m[a] <= a; q <= m[a]; end endmodule',
])
def test_refusal_preserves_database(tmp_path, body):
    source = tmp_path / 'bad.sv'
    source.write_text(body)
    out = tmp_path / 'design.db'
    out.write_bytes(b'previous database')
    with pytest.raises(ValueError):
        build_hdl([source], 'top', out, yosys=YOSYS)
    assert out.read_bytes() == b'previous database'
