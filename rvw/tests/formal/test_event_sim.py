from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import counts, events, run
from rvw.results import load_run


def test_events():
    data = dict(schema='rvw.formal-events/1', events=[dict(time=0, inputs=dict(clk='0', a='1')),
                                                   dict(time=1, inputs=dict(clk='1'))])
    assert len(events(data, dict(clk=1, a=1), {'clk'})[1]) == 2
    data['events'][1]['inputs']['a'] = '0'
    with pytest.raises(ValueError, match='separate timestamp'):
        events(data, dict(clk=1, a=1), {'clk'})


@pytest.mark.parametrize('backend', ['icarus', 'verilator'])
@pytest.mark.parametrize('mutant', [False, True])
def test_native_simulation(tmp_path, backend, mutant):
    if not shutil.which('yosys') or not shutil.which('iverilog' if backend == 'icarus' else 'verilator'):
        pytest.skip('native simulator and Yosys required')
    source = tmp_path / 'm.sv'
    source.write_text('''module m(input clk, other, irq, rst, a, output reg q=0);
always @(posedge other or posedge rst) if (rst) q <= 0; else q <= a;
property hold; @(posedge clk) a |=> a; endproperty
p: assert property (hold);
c: cover property (@(posedge irq) a);
endmodule''')
    rows = [dict(time=0, inputs=dict(clk='0',other='0',irq='0',rst='0',a='1')),
            dict(time=1, inputs=dict(clk='1')),
            dict(time=2, inputs=dict(clk='0',other='1')),
            dict(time=3, inputs=dict(irq='1')),
            dict(time=4, inputs=dict(irq='0',other='0')),
            dict(time=5, inputs=dict(a='0' if mutant else '1')),
            dict(time=6, inputs=dict(clk='1')),
            dict(time=7, inputs=dict(rst='1'))]
    plan = tmp_path / 'events.json'
    plan.write_text(json.dumps(dict(schema='rvw.formal-events/1', clocks=['clk','other','irq'], events=rows)))
    out = tmp_path / 'out'
    code = run(Namespace(verilog=[str(source)], top='m', events=str(plan), out=str(out),
                         backend=backend, observe=None, check_x=backend == 'icarus', timeout=60))
    result = load_run(out)
    assert result.status == ('assert' if mutant else 'pass')
    assert code == int(mutant)
    assert result.extra['assertions'][0]['failed'] == int(mutant)
    assert result.extra['assertions'][1]['covered'] == 1
    assert result.extra['observations'][-1]['value'] == '0'
    from rvw.cov.code import read_counts
    assert sum(read_counts(out / 'coverage.dat').values()) >= 1
    if not mutant:
        from rvw.cov.code import merge
        assert len(merge([str(out)], root=out)['points']) == 2


def test_no_forged_counts():
    with pytest.raises(ValueError):
        counts('RVW_SVA invented assert pass\n', [])


def test_native_unknown_observation(tmp_path):
    if not shutil.which('yosys') or not shutil.which('iverilog'):
        pytest.skip('Icarus and Yosys required')
    source = tmp_path / 'x.sv'
    source.write_text('module m(input clk, output reg q); always @(posedge clk) q<=1; endmodule')
    plan = tmp_path / 'events.json'
    plan.write_text(json.dumps(dict(schema='rvw.formal-events/1', clocks=['clk'], events=[
        dict(time=0, inputs=dict(clk='0')), dict(time=1, inputs=dict(clk='1'))])))
    out = tmp_path / 'out'
    assert run(Namespace(verilog=[str(source)], top='m', events=str(plan), out=str(out),
                         backend='icarus', observe=None, check_x=True, timeout=30)) == 1
    result = load_run(out)
    assert result.status == 'fail'
    assert result.extra['unknowns'] == [dict(time=0, signal='q', value='x')]
