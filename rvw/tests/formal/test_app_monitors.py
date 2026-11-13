import json
import shutil
from argparse import Namespace
import pytest
from rvw.formal.apps import generate, run
from rvw.formal.autocheck import expand


def plan():
    ports = {n: {'direction': 'input', 'width': 1} for n in ('clk', 'reset', 'push', 'pop')}
    ports.update({n: {'direction': 'output', 'width': 4} for n in ('a', 'b', 'data')})
    return {'schema': 'rvw.formal-apps/1', 'top': 'Top', 'clock': 'clk', 'reset': 'reset', 'ports': ports}


def test_filtered_contracts_and_toggle_candidates():
    spec = dict(plan(), schema='rvw.autocheck/1', toggle=True, contracts=[
        dict(id='bounds', kind='array_bound', signal='a', size=7),
        dict(id='sum', kind='arithmetic_overflow', signal='a', other='b', signed=True)])
    expanded = expand(spec, kinds=['array_bound', 'arithmetic_overflow', 'toggle'])
    assert len(expanded['properties']) == 14
    for prop in expanded['properties']:
        assert 'assert (' in generate(expanded, prop)


def test_invalid_fifo_and_array_parameters():
    with pytest.raises(ValueError, match='array bound'):
        generate(plan(), dict(kind='array_bound', signal='a', size=17))
    with pytest.raises(ValueError, match='FIFO'):
        generate(plan(), dict(kind='fifo', push='push', pop='pop', write_data='a', read_data='data', capacity=0))


@pytest.mark.parametrize('kind,a,b,signed,expected', [
    ('onehot', 2, 0, False, 'pass'), ('onehot', 3, 0, False, 'fail'),
    ('mutex', 0, 0, False, 'pass'), ('toggle', 2, 0, False, 'pass'), ('arithmetic_overflow', 7, 1, True, 'fail'),
    ('arithmetic_overflow', 8, 7, True, 'pass'), ('arithmetic_overflow', 15, 1, False, 'fail'),
    ('array_bound', 8, 0, False, 'fail')])
def test_native_monitors(tmp_path, kind, a, b, signed, expected):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'z3')):
        pytest.skip('native formal tools required')
    spec = plan()
    (tmp_path / 'Top.sv').write_text(f'module Top(input clk,reset,push,pop,output [3:0] a,b,data); assign a=4\'d{a}; assign b=4\'d{b}; assign data=0; endmodule')
    prop = dict(id='check', kind=kind, signal='a', other='b', signed=signed, size=7, bit=0)
    spec.update(verilog=['Top.sv'], properties=[prop])
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(spec))
    out = tmp_path / 'out'
    run(Namespace(manifest=str(path), out=str(out), depth=4, engine='smtbmc:z3', timeout=15, mode='bmc', json=False))
    report = json.loads((out / 'result.json').read_text())
    assert report['properties'][0]['status'] == expected


def test_all_waived_runs_no_solver(tmp_path, monkeypatch):
    import rvw.formal.apps as apps
    monkeypatch.setattr(apps, 'flow', lambda *a, **kw: pytest.fail('waived property ran a solver'))
    spec = plan()
    source = tmp_path / 'Top.sv'
    source.write_text('module Top; endmodule')
    spec.update(verilog=['Top.sv'], properties=[dict(id='one', kind='onehot', signal='a')], waivers={'one': 'reviewed external invariant'})
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(spec))
    out = tmp_path / 'out'
    assert run(Namespace(manifest=str(path), out=str(out), depth=4, engine='smtbmc:z3', timeout=15, mode='bmc', json=False)) == 1
    report = json.loads((out / 'result.json').read_text())
    assert report['status'] == 'no_checks' and report['properties'][0]['status'] == 'waived'


@pytest.mark.parametrize('corrupt,expected', [(False, 'pass'), (True, 'fail'), ('overflow', 'fail'), ('underflow', 'fail')])
def test_native_fifo_ordering(tmp_path, corrupt, expected):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'z3')):
        pytest.skip('native formal tools required')
    spec = plan()
    spec['ports']['push']['direction'] = 'output'
    spec['ports']['pop']['direction'] = 'output'
    spec['ports']['a']['direction'] = 'input'
    spec['ports'].update({n: {'direction': 'input', 'width': 1} for n in ('request_push', 'request_pop')})
    (tmp_path / 'Top.sv').write_text('''module Top(input clk,reset,request_push,request_pop,input [3:0] a,
output push,pop,output [3:0] b,data);
reg [3:0] mem[0:1]; reg rd=0,wr=0; reg [1:0] count=0;
assign b=0; assign push=request_push && count<2; assign pop=request_pop && count>0;
assign data=mem[rd]''' + (" ^ 4'd1" if corrupt is True else '') + ''';
always @(posedge clk) if(reset) begin count<=0; rd<=0; wr<=0; end
else begin
 if(push) begin mem[wr]<=a; wr<=!wr; end
 if(pop) rd<=!rd;
 case({push,pop}) 2'b10: count<=count+1; 2'b01: count<=count-1; endcase
end endmodule''')
    if corrupt in ('overflow', 'underflow'):
        rtl = tmp_path / 'Top.sv'
        text = rtl.read_text()
        text = text.replace('push=request_push && count<2', 'push=1') if corrupt == 'overflow' else text.replace('pop=request_pop && count>0', 'pop=1')
        rtl.write_text(text)
    spec.update(verilog=['Top.sv'], properties=[dict(id='fifo', kind='fifo', push='push', pop='pop', write_data='a', read_data='data', capacity=2)])
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(spec))
    out = tmp_path / 'out'
    run(Namespace(manifest=str(path), out=str(out), depth=6, engine='smtbmc:z3', timeout=20, mode='bmc', json=False))
    report = json.loads((out / 'result.json').read_text())
    assert report['properties'][0]['status'] == expected


def test_bounded_starvation_and_handshake_refuse_fairness():
    spec = plan()
    prop = dict(kind='arbiter_starvation', request='push', grant='pop', bound=3)
    assert 'rvwa_age' in generate(spec, prop)
    with pytest.raises(ValueError, match='general liveness'):
        generate(spec, dict(prop, fairness='pop'))
    assert 'rvwa_age' in generate(spec, dict(kind='handshake_progress', valid='push', ready='pop', bound=3))


def test_boolean_options_do_not_change_meaning_from_strings():
    with pytest.raises(ValueError, match='boolean'):
        generate(plan(), dict(kind='onehot', signal='a', allow_zero='false'))
    with pytest.raises(ValueError, match='boolean'):
        generate(plan(), dict(kind='arithmetic_overflow', signal='a', other='b', signed='false'))
