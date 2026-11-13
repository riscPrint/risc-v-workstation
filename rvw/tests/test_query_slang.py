"""slang (yosys-slang) front end of `rvw query build-hdl`: full SV, includes, defines, parameters."""
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil

import pytest

from rvw.cli import main
from rvw.query import ops
from rvw.query.db import DesignDB
from rvw.query.hdl import build_hdl
from rvw.query.hdl_slang import instances, parse_ast

YOSYS = shutil.which('yosys')


def _has_slang():
    if not YOSYS:
        return False
    if os.environ.get('RVW_SLANG'):
        return True
    return (Path(os.path.realpath(YOSYS)).parents[1] / 'share/yosys/plugins/slang.so').is_file()


needs_slang = pytest.mark.skipif(not _has_slang(), reason='native Yosys with the yosys-slang plugin required')

DEFS = '`define NEXT(x) ((x) + 1\'b1)\n'
TOP = '''`include "defs.svh"
package p;
  typedef enum logic [1:0] {IDLE, RUN, DONE} state_e;
endpackage
module leaf import p::*; #(parameter int W = 4) (
  input  logic clk_i, rst_ni,
  input  logic [W-1:0] d_i,
  output logic [W-1:0] q_o,
  output state_e st_o);
  state_e st_q;
  logic [W-1:0] tbl [4];
  always_ff @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) begin q_o <= '0; st_q <= IDLE; end
    else begin
      q_o <= `NEXT(d_i);
      st_q <= st_q == IDLE ? RUN : DONE;
    end
  always_ff @(posedge clk_i) tbl[d_i[1:0]] <= d_i;
  assign st_o = st_q;
endmodule
module top #(parameter int N = 2) (
  input  logic clk_i, rst_ni,
  input  logic [7:0] a_i, b_i,
  output logic [8*N-1:0] y_o);
  for (genvar i = 0; i < N; i++) begin : g
`ifdef EXTRA
    leaf #(.W(8)) u (.clk_i, .rst_ni, .d_i(a_i ^ 8'(i)), .q_o(y_o[i*8 +: 8]), .st_o());
`else
    assign y_o[i*8 +: 8] = a_i;
`endif
  end
endmodule
'''


def _design(tmp_path):
    (tmp_path / 'inc').mkdir()
    (tmp_path / 'inc/defs.svh').write_text(DEFS)
    (tmp_path / 'rtl').mkdir()
    source = tmp_path / 'rtl/top.sv'
    source.write_text(TOP)
    return source


def test_ast_parameters_and_types():
    ast = {'members': [{'kind': 'CompilationUnit'}, {'kind': 'Instance', 'name': 'top', 'body': {'members': [
        {'kind': 'Parameter', 'name': 'N', 'value': '2'},
        {'kind': 'Parameter', 'name': 'L', 'value': '1', 'isLocal': True},
        {'kind': 'Variable', 'name': 'x', 'type': 'logic[3:0]'},
        {'kind': 'GenerateBlock', 'name': 'off', 'isUninstantiated': True, 'members': [
            {'kind': 'Instance', 'name': 'dead', 'body': {'members': []}}]},
        {'kind': 'GenerateBlockArray', 'name': 'g', 'members': [
            {'kind': 'GenerateBlock', 'constructIndex': 0, 'members': [
                {'kind': 'Instance', 'name': 'u', 'body': {'members': [
                    {'kind': 'Parameter', 'name': 'W', 'value': "32'd8"},
                    {'kind': 'Variable', 'name': 's', 'type': '123456 p::state_e'}]}}]}]}]}}]}
    params, types = instances(parse_ast('log line\n' + json.dumps(ast) + '\nBuild succeeded'))
    assert params == {'': {'N': '2'}, 'g[0].u': {'W': "32'd8"}}
    assert types == {'x': 'logic[3:0]', 'g[0].u.s': 'p::state_e'}


@needs_slang
def test_slang_full_sv(tmp_path, capsys):
    source = _design(tmp_path)
    out = tmp_path / 'design.db'
    build_hdl([source], 'top', out, yosys=YOSYS, frontend='slang', include_dirs=[tmp_path / 'inc'],
              defines=['EXTRA'], parameters=['N=3'])
    db = DesignDB(out)
    try:
        assert db.meta['frontend'] == 'yosys-slang'
        assert json.loads(db.meta['hdl_options'])['parameters'] == ['N=3']
        kids = [c['path'] for c in ops.hierarchy(db)['root']['children']]
        assert kids == ['g[0].u', 'g[1].u', 'g[2].u']
        # Generate indexes resolve in both spellings.
        assert ops.component(db, 'g.1.u')['module'] == 'leaf'
        st = db.resolve_one('g[1].u.st_q')
        assert st.kind == 'reg' and st.type == 'p::state_e'
        assert ops.where(db, 'g[1].u.st_q')['signal']['loc'] == f'{source}:10'
        cd = db.clock_domain(st.clock_domain_id)
        assert cd['clock'] == 'clk_i' and cd['reset'] == 'rst_ni' and cd['reset_kind'] == 'ASYNC'
        assert ops.path(db, 'a_i', 'g[2].u.q_o')['found']
        assert not ops.path(db, 'b_i', 'g[2].u.q_o')['found']
        mem = ops.drivers(db, 'g[0].u.tbl')
        assert mem['signal']['kind'] == 'mem' and mem['memory']['depth'] == 4
        params = json.loads(db.q("SELECT content FROM artifacts WHERE name='hdl/parameters.json'")[0][0])
        assert params[''] == {'N': '3'} and params['g[2].u'] == {'W': '8'}
        assert ops.component(db, 'g[2].u')['parameters'] == {'W': '8'}
        # The include file came from the captured include directory.
        inputs = {r[0] for r in db.q('SELECT path FROM input_files')}
        assert str(tmp_path / 'inc/defs.svh') in inputs and str(source) in inputs
    finally:
        db.close()
    assert main(['query', 'drivers', 'g[0].u.q_o', '--db', str(out), '--json']) == 0
    assert 'error' not in json.loads(capsys.readouterr().out)


@needs_slang
def test_slang_needs_define_and_include(tmp_path):
    source = _design(tmp_path)
    out = tmp_path / 'design.db'
    out.write_bytes(b'previous database')
    with pytest.raises(ValueError, match='elaboration failed'):
        build_hdl([source], 'top', out, yosys=YOSYS, frontend='slang')  # no include directory
    assert out.read_bytes() == b'previous database'
    with pytest.raises(ValueError, match='need --frontend slang'):
        build_hdl([source], 'top', out, yosys=YOSYS, include_dirs=[tmp_path / 'inc'])
    with pytest.raises(ValueError, match='unsupported define'):
        build_hdl([source], 'top', out, yosys=YOSYS, frontend='slang', defines=['A B'])


def _oracle(netlist, top):
    """Independent reachability over the slang netlist bits (whole cells, ports by direction)."""
    modules = json.loads(Path(netlist).read_text())['modules']
    graph, names = defaultdict(set), {}

    def visit(module, scope):
        m = modules[module]
        for name, net in m['netnames'].items():
            names[(scope + '.' if scope else '') + name] = {(scope, b) for b in net['bits'] if isinstance(b, int)}
        for name, cell in m['cells'].items():
            if cell['type'] in modules:
                child = (scope + '.' if scope else '') + name
                visit(cell['type'], child)
                for port, bb in cell['connections'].items():
                    cp = modules[cell['type']]['ports'][port]
                    for pb, cb in zip(bb, cp['bits']):
                        if isinstance(pb, int) and isinstance(cb, int):
                            a, b = (scope, pb), (child, cb)
                            if cp['direction'] == 'input':
                                graph[a].add(b)
                            else:
                                graph[b].add(a)
            else:
                ins, outs = set(), set()
                for port, bb in cell['connections'].items():
                    if port in ('CLK', 'ALOAD', 'ARST'):
                        continue
                    (ins if cell['port_directions'][port] == 'input' else outs).update(
                        (scope, b) for b in bb if isinstance(b, int))
                if cell['type'].startswith(('$memwr', '$memrd')):
                    # A memory links its write-port inputs to its read-port outputs.
                    mem = (scope, 'mem', cell['parameters']['MEMID'])
                    if cell['type'].startswith('$memwr'):
                        outs = {mem}
                    else:
                        ins = ins | {mem}
                for a in ins:
                    graph[a].update(outs)
    visit(top, '')

    def reachable(a, b):
        todo, seen = list(names[a]), set(names[a])
        while todo:
            for nxt in graph[todo.pop()]:
                if nxt in names[b]:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return False
    return reachable


@needs_slang
def test_slang_matches_netlist_oracle(tmp_path):
    from rvw.common.proc import run_group
    source = _design(tmp_path)
    out = tmp_path / 'design.db'
    build_hdl([source], 'top', out, yosys=YOSYS, frontend='slang', include_dirs=[tmp_path / 'inc'],
              defines=['EXTRA'])
    netlist = tmp_path / 'oracle.json'
    script = tmp_path / 'oracle.ys'
    script.write_text(f'read_slang --keep-hierarchy --ignore-assertions --top top -I {tmp_path / "inc"} -D EXTRA '
                      f'{source}\nproc\nwrite_json {netlist}\n')
    p = run_group([YOSYS, '-Q', '-T', '-m', 'slang', '-s', str(script)], capture=True, timeout=60)
    assert p.returncode == 0, p.stderr
    oracle = _oracle(netlist, 'top')
    db = DesignDB(out)
    try:
        for a in ('a_i', 'b_i', 'rst_ni', 'g[0].u.d_i', 'g[1].u.st_q'):
            for b in ('y_o', 'g[0].u.q_o', 'g[1].u.st_o', 'g[1].u.q_o'):
                assert ops.path(db, a, b)['found'] == oracle(a, b), (a, b)
    finally:
        db.close()


@needs_slang
def test_ibex_core(tmp_path):
    root = Path(os.environ.get('RVW_HDL_REF', Path(__file__).parents[3] / 'ref')) / 'ibex'
    prim = root / 'vendor/lowrisc_ip/ip/prim/rtl'
    if not (root / 'rtl/ibex_core.sv').exists():
        pytest.skip('ibex read-only reference checkout is absent; set RVW_HDL_REF')
    skip = ('pkg', 'tracer', 'top', 'lockstep', 'fpga', 'latch', 'icache')
    sources = [prim / 'prim_util_pkg.sv', *sorted((root / 'rtl').glob('*_pkg.sv')),
               *[p for p in sorted((root / 'rtl').glob('*.sv')) if not any(s in p.name for s in skip)]]
    sources = [p for p in sources if 'tracer' not in p.name]
    out = tmp_path / 'ibex.db'
    build_hdl(sources, 'ibex_core', out, yosys=YOSYS, frontend='slang', timeout=300,
              include_dirs=[prim, root / 'vendor/lowrisc_ip/dv/sv/dv_utils'])
    db = DesignDB(out)
    try:
        names = {c['name'] for c in ops.hierarchy(db, depth=1)['root']['children']}
        assert {'if_stage_i', 'id_stage_i', 'ex_block_i', 'cs_registers_i'} <= names
        mepc = db.resolve_one('cs_registers_i.u_mepc_csr.rdata_q')
        assert mepc.kind == 'reg' and mepc.width == 32
        assert db.clock_domain(mepc.clock_domain_id)['reset_kind'] == 'ASYNC'
        assert ops.drivers(db, 'cs_registers_i.u_mepc_csr.rdata_q')['assignments']
        params = json.loads(db.q("SELECT content FROM artifacts WHERE name='hdl/parameters.json'")[0][0])
        assert params['cs_registers_i.u_mepc_csr']['Width'] == "32'd32"
    finally:
        db.close()


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
def test_mcp_build_hdl(tmp_path):
    from rvw.query.mcp_tools import mcp_tools
    source = tmp_path / 'a.v'
    source.write_text('module top(input a, output b); assign b = ~a; endmodule\n')
    spec = next(t for t in mcp_tools() if t.name == 'query_build_hdl')
    r = spec.handler(sources=[str(source)], top='top', out=str(tmp_path / 'a.db'))
    assert r['frontend'] == 'yosys-verilog' and r['info']['counts']['components'] == 1
