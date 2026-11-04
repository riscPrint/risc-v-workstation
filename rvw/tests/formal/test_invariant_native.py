"""Reference specifications and independent seeded faults for every monitor."""
import json
import shutil
import sys

import pytest
from rvw.common.proc import run_group
from rvw.formal.invariants import render


@pytest.mark.parametrize('kind', ['rob', 'credit', 'freelist', 'rename', 'issue', 'lsq'])
@pytest.mark.parametrize('bad', [False, True])
def test_reference(tmp_path, kind, bad):
    if not all(shutil.which(t) for t in ('sby', 'yosys', 'yices-smt2')):
        pytest.skip('native formal tools missing')
    monitor = tmp_path / 'monitor.sv'
    monitor.write_text(render(kind))
    if kind in ('rob', 'credit'):
        body = '''reg [2:0] count=0;
wire push = step && count < 4;
wire pop = !step && count > 0;
always @(posedge clk) if(reset) count<=0;
else count <= count + (push ? 1 : 0) - (pop ? 1 : 0);'''
        if bad:
            body = body.replace('count + (push ? 1 : 0)', 'count + (push ? 2 : 0)')
        conn = '.count(count), .push(push), .pop(pop)'
    elif kind == 'freelist':
        body = "wire [3:0] free_bits = step ? 4'b0011 : 4'b1100;\n"
        body += "wire [3:0] allocated = " + ('free_bits;' if bad else '~free_bits;')
        conn = '.free_bits(free_bits), .allocated(allocated)'
    elif kind == 'rename':
        body = "wire [3:0] valid = 4'b1111; wire [11:0] tags = " + ("12'o0012;" if bad else "12'o0123;")
        conn = '.valid(valid), .tags(tags)'
    elif kind == 'issue':
        body = "wire [3:0] valid=4'b1111, ready=4'b0101; wire [3:0] issued = " + ("4'b0011;" if bad else "(step ? 4'b0001 : 4'b0100);")
        conn = '.valid(valid), .ready(ready), .issued(issued)'
    else:
        body = ''
        conn = ".load_fire(step), .older_store(1'b1), .address_match(1'b1), .forwarded(1'b1), .load_data(" + ("3'd2" if bad else "3'd1") + "), .store_data(3'd1)"
    source = tmp_path / 'top.sv'
    source.write_text('module Top(input clk, reset, step);\n' + body +
                      f'\nrvw_{kind} monitor(.clk(clk), .reset(reset), {conn});\nendmodule\n')
    out = tmp_path / 'out'
    result = run_group([sys.executable, '-m', 'rvw', 'formal', 'prove', '--verilog',
                        str(source), str(monitor), '--top', 'Top', '--engine', 'smtbmc:yices',
                        '--depth', '8', '--timeout', '20', '--out', str(out)], capture=True, timeout=45)
    assert result.returncode == int(bad), (result.stdout, result.stderr)
    data = json.loads((out / 'result.json').read_text())
    assert data['status'] == ('fail' if bad else 'pass')
    assert data['proof_kind'] == 'unbounded'
    if bad:
        assert data['traces']
