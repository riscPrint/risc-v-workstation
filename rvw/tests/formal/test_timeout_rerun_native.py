"""Native replay controls. Put --basetemp outside /tmp to retain small evidence."""
import json
import shutil
import pytest
from rvw.formal.timeout_rerun import run


@pytest.mark.native_light('Yosys')
def test_three_replay_controls(tmp_path):
    if not all(shutil.which(t) for t in ('sby','yosys','yosys-abc','bitwuzla')):
        pytest.skip('native SBY, Yosys, ABC and Bitwuzla required')
    previous=[]
    toggle='reg a=0,b=0; always @(posedge clk) begin a<=!a; b<=!b; assert(a==b); end'
    for name,mode,body in [('inductive','prove',toggle),('bounded','bmc',toggle),
                           ('negative','bmc','always @(posedge clk) assert(0);')]:
        (tmp_path/(name+'.sv')).write_text('module top(input clk); '+body+' endmodule\n')
        (tmp_path/(name+'.sby')).write_text(f'[options]\nmode {mode}\ndepth 5\n[engines]\nsmtbmc bitwuzla\n[script]\nread -formal {name}.sv\nprep -top top\n[files]\n{name}.sv\n')
        previous.append(dict(id=name,status='timeout'))
    (tmp_path/'previous.json').write_text(json.dumps(dict(tests=previous)))
    plan=dict(cores=[dict(name='synthetic-replay-controls',previous='previous.json',jobs='.')])
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    report=run(plan,tmp_path,tmp_path/'run',20)
    assert {r['check']:r['status'] for r in report['rows']} == {
        'bounded':'bounded_pass','inductive':'pass','negative':'fail'}
    assert all(r['engine'] and r['load_average_start'] and r['load_average_end'] for r in report['rows'])
