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


@pytest.mark.parametrize('command', ['contracts', 'strengthen', 'strengthen_bad_sample'])
def test_contract_and_mining_native(tmp_path, command):
    if not all(shutil.which(t) for t in ('sby', 'yosys', 'yices-smt2')):
        pytest.skip('native formal tools missing')
    source = tmp_path / 'units.sv'
    source.write_text('''module Producer(input clk, reset, output reg token=0);
always @(posedge clk) token <= reset ? 0 : 1;
endmodule
module Consumer(input clk, reset, token, output accepted);
assign accepted = token;
endmodule
''')
    # Producer's guarantee applies after reset; token is 0 on the release edge.
    # Use a combinational producer to avoid an unstated latency contract.
    source.write_text(source.read_text().replace('output reg token=0', 'output token')
                      .replace('always @(posedge clk) token <= reset ? 0 : 1;', 'assign token = 1;'))
    plan = {'verilog': ['units.sv'], 'signals': {'token': 1, 'accepted': 1},
            'predicates': {'token_ok': 'token == 1', 'accepted_ok': 'accepted == 1'},
            'components': [
                {'id': 'producer', 'top': 'Producer', 'inputs': [], 'outputs': ['token'],
                 'assumes': [], 'guarantees': ['token_ok']},
                {'id': 'consumer', 'top': 'Consumer', 'inputs': ['token'], 'outputs': ['accepted'],
                 'assumes': ['token_ok'], 'guarantees': ['accepted_ok']} ]}
    if command.startswith('strengthen'):
        plan['components'] = plan['components'][:1]
        plan['samples'] = [{'token': 0 if command.endswith('bad_sample') else 1}]
    manifest = tmp_path / 'plan.json'
    manifest.write_text(json.dumps(plan))
    out = tmp_path / 'out'
    result = run_group([sys.executable, '-m', 'rvw', 'formal', command.split('_bad_sample')[0], str(manifest),
                        '--engine', 'smtbmc:yices', '--budget', '30', '--out', str(out), '--json'],
                       capture=True, timeout=60)
    assert result.returncode == 0, (result.stdout, result.stderr)
    data = json.loads(result.stdout)
    assert data['status'] == ('conditional_proved' if command == 'contracts' else 'pass')
    if command.startswith('strengthen'):
        assert data['certified'] == ([] if command.endswith('bad_sample') else ['bound_token'])
        if command.endswith('bad_sample'):
            assert data['obligations'][0]['status'] == 'fail'
