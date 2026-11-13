"""Lint rules on native Yosys imports: aliases, constant ties and slice-only vector logic."""
import shutil
import pytest
from rvw.lint import rules
from rvw.query.db import run_on
from rvw.query.hdl import build_hdl

YOSYS = shutil.which('yosys')

SV = '''module leaf(input en, input [1:0] a, output [2:0] y, output tied);
  wire s = !(en | a[0]);
  assign y = {~s, a[1] & s, a[0] | s};   // slices of y depend on s, not on y
  assign tied = 1'b0;
endmodule
module top(input clk, input en, input [1:0] a, output [2:0] y, output t, output z, output loop);
  wire co, o;
  assign co = en;
  assign o = co;                       // shared alias name
  wire [1:0] k;
  assign k = 2'b01;
  leaf u(.en(o), .a(k), .y(y), .tied(t));
  reg [3:0] count;
  always @(posedge clk) count <= count + 1;
  assign z = count[3];
  wire w;
  assign w = ~w & en;                  // a real combinational loop
  assign loop = w;
endmodule
'''


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
def test_hdl_import_lint(tmp_path):
    src = tmp_path / 'top.v'
    src.write_text(SV)
    db = tmp_path / 'top.db'
    build_hdl([src], 'top', db, yosys=YOSYS)
    r = run_on(db, lambda d: rules.analyze(d, {}))
    found = {(f['rule'], f['endpoint']) for f in r['findings']}
    loops = [f for f in r['findings'] if f['rule'] == 'lint.comb_loop']
    assert len(loops) == 1 and 'w' in loops[0]['members']
    assert not {x for x in found if x[0] in ('lint.undriven', 'lint.unused', 'lint.unconnected_output',
                                             'lint.input_driven')}, found
    from rvw.lint import structural
    s = run_on(db, lambda d: structural.analyze(d, {}))
    assert s['registers'] >= 1 and s['domains'][0]['clock'] == 'clk'
