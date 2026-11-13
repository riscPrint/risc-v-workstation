"""Out-of-order rule templates: rendering, binding, and firing in a small simulation."""
import json
import re
import shutil
import subprocess

import pytest

from rvw.formal import ooo_checks
from rvw.formal.micro_checks import generate

pytestmark = pytest.mark.fast


def firing(source):
    return re.sub(r'assert\(([^;]*)\);', r'if(!(\1)) $display("FIRE %m");', source)


def simulate(tmp_path, source, bench):
    if not shutil.which('iverilog'):
        pytest.skip('iverilog is not installed')
    (tmp_path / 'm.v').write_text(firing(source))
    (tmp_path / 'tb.v').write_text(bench)
    subprocess.run(['iverilog', '-g2012', '-o', str(tmp_path / 'a.out'), str(tmp_path / 'm.v'), str(tmp_path / 'tb.v')],
                   check=True, capture_output=True, text=True)
    out = subprocess.run(['vvp', '-n', str(tmp_path / 'a.out')], check=True, capture_output=True, text=True).stdout
    return out.count('FIRE')


def test_rob_pointers_two_lane_step(tmp_path):
    src = ooo_checks.render('rob_pointers', 7, 8, {'push_step': 2, 'pop_step': 2})
    assert 'module rvw_rob_pointers' in src

    def bench(rows):
        steps = '\n'.join(f' @(negedge clk) a={a}; f={f}; push={u}; pop={o};' for a, f, u, o in rows)
        return f'''module tb; reg clk=0, reset=1; reg [3:0] a=0, f=0; reg push=0, pop=0;
rvw_rob_pointers dut(.clk(clk), .reset(reset), .alloc_ptr(a), .free_ptr(f), .push(push), .pop(pop));
always #1 clk=~clk;
initial begin
 @(negedge clk) reset=0;
{steps}
 #4 $finish;
end
endmodule
'''
    good = [(0, 0, 1, 0), (2, 0, 1, 1), (4, 2, 1, 0), (6, 2, 1, 1), (8, 4, 1, 0), (10, 4, 1, 1), (12, 6, 0, 0)]
    assert simulate(tmp_path, src, bench(good)) == 0
    assert simulate(tmp_path, src, bench([(0, 0, 1, 0), (4, 0, 0, 0)])) > 0      # alloc moved by 4
    assert simulate(tmp_path, src, bench([(0, 0, 1, 0), (2, 0, 0, 1), (2, 4, 0, 0)])) > 0  # free passes alloc
    full = [(2 * i, 0, 1, 0) for i in range(4)] + [(8, 0, 1, 0)]
    assert simulate(tmp_path, src, bench(full)) > 0                                 # push into a full ROB


def test_freelist_ghost_catches_double_free_and_stale_allocation(tmp_path):
    src = ooo_checks.render('freelist_ghost', 3, 8, {'alloc_lanes': 2, 'free_lanes': 2})

    def bench(events):
        steps = '\n'.join(f' @(negedge clk) {e}' for e in events)
        return f'''module tb; reg clk=0, reset=1; reg fire=0; reg [1:0] av=0, fv=0; reg [5:0] at=0, ft=0;
rvw_freelist_ghost dut(.clk(clk), .reset(reset), .alloc_fire(fire), .alloc_valid(av), .alloc_tags(at), .free_valid(fv), .free_tags(ft));
always #1 clk=~clk;
initial begin
 @(negedge clk) reset=0;
{steps}
 @(negedge clk) fire=0; av=0; fv=0; #4 $finish;
end
endmodule
'''
    fill = ["fv=2'b11; ft={3'd1,3'd0};", "fv=2'b11; ft={3'd3,3'd2};", 'fv=0;']
    good = fill + ["fire=1; av=2'b11; at={3'd1,3'd0};", "fire=0; av=0; fv=2'b01; ft={3'd0,3'd0};"]
    assert simulate(tmp_path, src, bench(good)) == 0
    double = fill + ["fv=2'b01; ft={3'd0,3'd2};"]
    assert simulate(tmp_path, src, bench(double)) > 0
    stale = fill + ["fire=1; av=2'b01; at={3'd0,3'd5};"]
    assert simulate(tmp_path, src, bench(stale)) > 0


def test_store_forward_window_age(tmp_path):
    src = ooo_checks.render('store_forward_window', 8, 4)

    def bench(hits, selected, start, end):
        return f'''module tb; reg clk=0, reset=1, active=0; reg [3:0] h=0, s=0; reg [2:0] st=0, en=0;
rvw_store_forward_window dut(.clk(clk), .reset(reset), .active(active), .is_load(1'b1), .hits(h), .selected(s), .start_ptr(st), .end_ptr(en));
always #1 clk=~clk;
initial begin
 @(negedge clk) reset=0; active=1; h={hits}; s={selected}; st={start}; en={end};
 @(negedge clk) active=0; #4 $finish;
end
endmodule
'''
    # Store cycles carry unrelated load-window signals and must not be checked.
    inactive = bench("4'b0100", "4'b0100", 3, 6).replace(".is_load(1'b1)", ".is_load(1'b0)")
    assert simulate(tmp_path, src, inactive) == 0
    # Window [3, 6) wraps entries 3, 0, 1 (end 6 = entry 2 after one wrap); youngest older is entry 1.
    assert simulate(tmp_path, src, bench("4'b0011", "4'b0010", 3, 6)) == 0
    assert simulate(tmp_path, src, bench("4'b0011", "4'b0001", 3, 6)) > 0   # oldest selected
    assert simulate(tmp_path, src, bench("4'b0100", "4'b0100", 3, 6)) > 0   # entry 2 is not older
    assert simulate(tmp_path, src, bench("4'b0011", "4'b0000", 3, 6)) > 0   # hit without forwarding


def test_generate_binds_lane_lists(tmp_path):
    spec = {'schema': 'rvw.micro-checks/1', 'top': 'Core', 'rules': [
        {'id': 'rf', 'kind': 'freelist_ghost', 'entries': 64, 'width': 6, 'lanes': {'alloc_lanes': 2, 'free_lanes': 2},
         'ports': {'clk': 'clk', 'reset': 'reset', 'alloc_fire': 'fire', 'alloc_valid': 'mask',
                   'alloc_tags': ['pop0', 'pop1'], 'free_valid': ['push0_v', 'push1_v'], 'free_tags': ['push0', 'push1']}},
        {'id': 'rob', 'kind': 'rob_pointers', 'entries': 64, 'lanes': {'push_step': 2, 'pop_step': 2},
         'ports': {'clk': 'clk', 'reset': 'reset', 'alloc_ptr': 'a', 'free_ptr': 'f', 'push': 'p', 'pop': 'q'}},
        {'id': 'bad', 'kind': 'store_forward_window', 'entries': 16,
         'ports': {'clk': 'clk', 'reset': 'reset', 'active': 'x', 'is_load': 'load', 'hits': ['h', 'not a name'], 'selected': 's',
                   'start_ptr': 'b', 'end_ptr': 'e'}}]}
    r = generate(spec, tmp_path / 'out')
    assert [x['status'] for x in r['rules']] == ['generated', 'generated', 'unsupported']
    assert not r['complete']
    binds = (tmp_path / 'out' / 'binds.sv').read_text()
    assert '.alloc_tags({pop1, pop0})' in binds and '.free_valid({push1_v, push0_v})' in binds
    assert 'module rvw_rule_rob' in (tmp_path / 'out' / 'monitors.sv').read_text()
    assert json.loads((tmp_path / 'out' / 'result.json').read_text())['rules'][0]['lanes'] == {'alloc_lanes': 2, 'free_lanes': 2}


def test_invalid_parameters():
    with pytest.raises(ValueError, match='power of two'):
        ooo_checks.render('rob_pointers', 7, 48)
    with pytest.raises(ValueError, match='lanes times step'):
        ooo_checks.render('rob_pointers', 7, 4, {'push_lanes': 3, 'push_step': 2})
    with pytest.raises(ValueError, match='tag width'):
        ooo_checks.render('freelist_ghost', 3, 16)
