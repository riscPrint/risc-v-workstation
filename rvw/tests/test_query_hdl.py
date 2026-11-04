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


def _yosys_graph(sources, top, tmp_path):
    """Independent oracle: traverse native bit IDs, never the imported SQL graph."""
    from collections import defaultdict
    from rvw.common.proc import run_group
    output = tmp_path / 'oracle.json'
    script = tmp_path / 'oracle.ys'
    script.write_text('read_verilog -sv ' + ' '.join('"'+str(p)+'"' for p in sources)
                      + f'\nhierarchy -check -top {top}\nproc\nwrite_json "{output}"\n')
    p = run_group([YOSYS, '-Q', '-T', '-s', str(script)], capture=True, timeout=60)
    assert p.returncode == 0, p.stderr
    modules = json.loads(output.read_text())['modules']
    graph, names = defaultdict(set), {}

    def visit(module, scope):
        m = modules[module]
        node = lambda b: (scope,b)
        for name, net in m['netnames'].items():
            names[(scope+'.' if scope else '')+name] = {node(b) for b in net['bits'] if isinstance(b,int)}
        for name, cell in m['cells'].items():
            if cell['type'] in modules:
                child = (scope+'.' if scope else '')+name
                visit(cell['type'],child)
                for port, bb in cell['connections'].items():
                    cp = modules[cell['type']]['ports'][port]
                    for pb, cb in zip(bb,cp['bits']):
                        if isinstance(pb,int) and isinstance(cb,int):
                            a,b = node(pb),(child,cb)
                            graph[a if cp['direction']=='input' else b].add(b if cp['direction']=='input' else a)
            else:
                # Yosys port directions are the oracle. Ignore clock ports, as C6 does.
                ins, outs = set(), set()
                for port, bb in cell['connections'].items():
                    if port == 'CLK':
                        continue
                    target = ins if cell['port_directions'][port]=='input' else outs
                    target.update(node(b) for b in bb if isinstance(b,int))
                for a in ins:
                    graph[a].update(outs)
    visit(top,'')

    def reachable(a,b):
        todo, seen = list(names[a]), set(names[a])
        while todo:
            n = todo.pop()
            for nxt in graph[n]:
                if nxt in names[b]:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return False
    return reachable


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
def test_yosys_oracle(tmp_path):
    source = tmp_path / 'design.sv'
    source.write_text(SV)
    out = tmp_path / 'design.db'
    build_hdl([source], 'top', out, yosys=YOSYS)
    oracle = _yosys_graph([source], 'top', tmp_path)
    db = DesignDB(out)
    try:
        for a in ('a','b','sel','clk','q','r'):
            for b in ('q','r','u0.d','u1.d'):
                if a != b:
                    assert ops.path(db,a,b)['found'] == oracle(a,b), (a,b)
        from rvw.query.diff import diff_files
        assert diff_files(out,out)['summary']['identical'] is None
    finally:
        db.close()


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
@pytest.mark.parametrize('core', ['serv','ibex'])
def test_open_core_oracle(tmp_path, core):
    import os
    root = Path(os.environ.get('RVW_HDL_REF', Path(__file__).parents[3] / 'ref'))
    if core == 'serv':
        sources = sorted((root/'serv/rtl').glob('*.v'))
        top, a, b = 'serv_top', 'i_ibus_rdt', 'o_dbus_dat'
    else:
        sources = [root/'ibex/rtl/ibex_counter.sv']
        top, a, b = 'ibex_counter', 'counter_inc_i', 'counter_val_o'
    if not sources or not all(p.exists() for p in sources):
        pytest.skip(f'{core} read-only reference checkout is absent; set RVW_HDL_REF')
    out = tmp_path/'design.db'
    build_hdl(sources,top,out,yosys=YOSYS)
    oracle = _yosys_graph(sources,top,tmp_path)
    db = DesignDB(out)
    try:
        assert oracle(a,b)
        assert ops.path(db,a,b)['found']
        assert ops.drivers(db,b)['assignments']
        assert ops.loads(db,a)['readers']
        assert not oracle(b,a)
        assert not ops.path(db,b,a)['found']
        assert ops.where(db,a)['signal']['loc']
    finally:
        db.close()
