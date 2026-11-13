"""Short JVM emission and paired native checks for the Scala liveness API."""
from argparse import Namespace
import json
import os
import shutil
import subprocess

import pytest

from rvw.formal.liveness import lower_live,run


@pytest.fixture
def emitted(tmp_path):
    classpath=os.environ.get('RVW_SVA_TEST_CLASSPATH')
    if not classpath:
        pytest.skip('set RVW_SVA_TEST_CLASSPATH after SpinalChecks Test/compile')
    output=tmp_path/'properties.sv'
    process=subprocess.run(['nice','-n','10','java','-cp',classpath,
                            'spinalchecks.SvaUnboundedEmitSmoke',str(output)],
                           capture_output=True,text=True,timeout=20)
    assert process.returncode==0,process.stdout+process.stderr
    return output.read_text()


def test_shared_unbounded_frontend(emitted):
    _,rows,finite=lower_live('module m(input clk,req,a,b); '+emitted+'endmodule','m')
    assert [row['id'] for row in rows]==[
        'eventual','weak_until','strong_until_with','delay','consecutive',
        'goto_range','nonconsecutive_range','weak_count']
    assert not finite
    assert rows[1]['operator']=='until'
    assert rows[2]['operator']=='s_until_with'
    assert rows[3]['minimum']==1
    assert rows[5]['maximum']==rows[6]['maximum']==2
    assert rows[7]['strength']=='weak'


CASES=[
    ('eventual','a=1; b=phase==2','a=1; b=0'),
    ('weak_until','a=1; b=phase==2','a=0; b=phase==2'),
    ('strong_until_with','a=1; b=phase==2','a=phase<2; b=phase==2'),
    ('delay','a=1; b=phase==2','a=1; b=0'),
    ('consecutive','a=phase<2; b=phase==2','a=phase==0; b=phase==2'),
    ('goto_range','a=phase==2; b=phase==1','a=0; b=phase==1'),
    ('nonconsecutive_range','a=phase==2; b=phase==1','a=0; b=phase==1'),
]


@pytest.mark.parametrize('name,good,bad',CASES)
@pytest.mark.parametrize('mutant',[False,True])
def test_native_scala_properties(tmp_path,emitted,name,good,bad,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    statement=next(line for line in emitted.splitlines() if line.startswith(name+':'))
    assignments='; assign '.join((bad if mutant else good).split('; '))
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,reset,output a,b); reg [1:0] phase=0; '
                      'always @(posedge clk) if(reset)phase<=0; else phase<=phase+1; '
                      'wire req=phase==0; assign '+assignments+'; '+statement+'\nendmodule\n')
    out=tmp_path/'out'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=20,
                  backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12))
    result=json.loads((out/'result.json').read_text())
    assert result['observation']==('FAIL' if mutant else 'PASS'),result
    assert result['status']==('fail' if mutant else 'unknown')


@pytest.mark.parametrize('backend',['icarus','verilator'])
@pytest.mark.parametrize('pending',[False,True])
def test_native_simulation_from_scala(tmp_path,emitted,backend,pending):
    from rvw.formal.event_sim import run as simulate
    from rvw.results import load_run
    needed=('yosys','iverilog','vvp') if backend=='icarus' else ('yosys','verilator')
    if not all(shutil.which(tool) for tool in needed):
        pytest.skip('Yosys and selected native simulator required')
    statement=next(line for line in emitted.splitlines() if line.startswith('eventual:'))
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,req,a,b); '+statement+'\nendmodule\n')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(clk='0',req='1',a='1',b='0')),
        dict(time=1,inputs=dict(clk='1')),
        dict(time=2,inputs=dict(clk='0')),
        dict(time=3,inputs=dict(req='0',b='0' if pending else '1')),
        dict(time=4,inputs=dict(clk='1')),
    ])))
    out=tmp_path/'sim'
    simulate(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                       backend=backend,observe=None,check_x=False,timeout=30))
    result=load_run(out)
    assert result.status==('error' if pending else 'pass'),result.to_dict()
    assertion=result.extra['assertions'][0]
    assert assertion['id']=='eventual'
    assert assertion['passed']==int(not pending)
    assert assertion['pending']==int(pending)
