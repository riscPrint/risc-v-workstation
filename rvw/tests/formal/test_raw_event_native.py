from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


@pytest.mark.parametrize('backend',['icarus','verilator'])
@pytest.mark.parametrize('mutant',[False,True])
def test_native_raw_sampling(tmp_path,mutant,backend):
    needed=('yosys','iverilog','vvp') if backend=='icarus' else ('yosys','verilator')
    if not all(shutil.which(tool) for tool in needed):
        pytest.skip('Yosys and selected native simulator required')
    source=tmp_path/'m.sv'
    source.write_text('''module m(input clk, irq, rst, data, output q);
assign q=data;
p: assert property (@(data) data === 1'b'''+('1' if mutant else '0')+''');
u: assert property (@(posedge irq or negedge rst) !irq);
c: cover property (@(negedge irq) irq);
property sample; @(posedge clk) irq && data; endproperty
f: assert property (sample);
endmodule''')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1', clocks=['clk'],events=[
        dict(time=0,inputs=dict(clk='0',irq='0',rst='1',data='0')),
        dict(time=1,inputs=dict(data='1')),
        dict(time=2,inputs=dict(rst='0')),
        dict(time=3,inputs=dict(irq='1')),
        dict(time=4,inputs=dict(irq='0',clk='1')),
    ])))
    out=tmp_path/'out'
    code=run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                       backend=backend,observe=None,check_x=backend=='icarus',timeout=60))
    result=load_run(out)
    assert code==int(mutant),result.to_dict()
    assert result.status==('assert' if mutant else 'pass')
    checks={p['id']:p for p in result.extra['assertions']}
    assert checks['p']['failed']==int(mutant) and checks['p']['passed']==int(not mutant)
    assert checks['u']['passed']==2 and checks['u']['failed']==0
    assert checks['c']['covered']==1
    assert checks['f']['passed']==1
    assert len(result.extra['property_events'])==4


def test_native_raw_four_state_edge(tmp_path):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    source.write_text("module m(input irq, output q); assign q=irq; p: assert property (@(negedge irq) irq === 1'b1); endmodule")
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(irq='1')),dict(time=1,inputs=dict(irq='x')),
        dict(time=2,inputs=dict(irq='0')),dict(time=3,inputs=dict(irq='1')),
        dict(time=4,inputs=dict(irq='z')),
    ])))
    out=tmp_path/'out'
    run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                  backend='icarus',observe=None,check_x=True,timeout=30))
    result=load_run(out)
    check=result.extra['assertions'][0]
    assert check['passed']==2 and check['failed']==1,result.to_dict()
    assert result.status=='assert'
    assert [r['time'] for r in result.extra['unknowns']]==[1,4]


def test_failed_compile_cannot_reuse_counts(tmp_path,monkeypatch):
    if not shutil.which('yosys'):
        pytest.skip('Yosys required')
    from types import SimpleNamespace
    import rvw.formal.event_sim as module
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,output q); assign q=1; endmodule')
    event_file=tmp_path/'events.json'
    event_file.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[dict(time=0,inputs=dict(clk='0'))])))
    out=tmp_path/'out'
    out.mkdir()
    for name in ('coverage.dat','run.log'):
        (out/name).write_text('stale passed counts')
    monkeypatch.setattr(module,'run_group',lambda *a,**kw:SimpleNamespace(returncode=1,timed_out=False))
    run(Namespace(verilog=[str(source)],top='m',events=str(event_file),out=str(out),
                  backend='icarus',observe=None,check_x=True,timeout=30))
    assert load_run(out).status=='error'
    assert not (out/'coverage.dat').exists()
    assert not (out/'run.log').exists()


@pytest.mark.parametrize('check_x,irq',[(True,'0'),(False,'x')])
def test_verilator_four_state_requests_are_refused(tmp_path,check_x,irq):
    if not shutil.which('yosys'):
        pytest.skip('Yosys required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input irq,output q); assign q=irq; assert property (@(irq) !irq); endmodule')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[dict(time=0,inputs=dict(irq=irq))])))
    with pytest.raises(ValueError,match='four-state replay'):
        run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(tmp_path/'out'),
                      backend='verilator',observe=None,check_x=check_x,timeout=30))
