from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


def oracle(samples,operator,nonoverlap):
    passed=failed=pending=0
    for index,(req,_,_) in enumerate(samples):
        if not req:
            continue
        for _,hold,response in samples[index+int(nonoverlap):]:
            if response and (hold or not operator.endswith('_with')):
                passed+=1
                break
            if operator!='s_eventually' and not hold:
                failed+=1
                break
        else:
            pending+=1
    return passed,failed,pending


def replay(tmp_path,backend,expr,samples,kind='assert'):
    needed=('yosys','iverilog','vvp') if backend=='icarus' else ('yosys','verilator')
    if not all(shutil.which(tool) for tool in needed):
        pytest.skip('Yosys and selected native simulator required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,req,hold,response,output q); assign q=response; '
                      'property p; @(posedge clk) '+expr+'; endproperty '
                      'a: '+kind+' property(p); c: cover property(p); endmodule')
    rows=[]
    for index,(req,hold,response) in enumerate(samples):
        value=lambda v:v if isinstance(v,str) else str(int(v))
        values=dict(req=value(req),hold=value(hold),response=value(response))
        if index==0:
            rows.append(dict(time=0,inputs=dict(clk='0',**values)))
        else:
            rows += [dict(time=index*3-1,inputs=dict(clk='0')),dict(time=index*3,inputs=values)]
        rows.append(dict(time=index*3+1,inputs=dict(clk='1')))
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=rows)))
    out=tmp_path/'out'
    code=run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                       backend=backend,observe=None,check_x=False,timeout=60))
    return code,load_run(out)


@pytest.mark.parametrize('backend',['icarus','verilator'])
@pytest.mark.parametrize('operator',['s_eventually','until','until_with','s_until','s_until_with'])
@pytest.mark.parametrize('nonoverlap',[False,True])
@pytest.mark.parametrize('mutant',[False,True])
def test_native_live_obligations(tmp_path,backend,operator,nonoverlap,mutant):
    if operator=='s_eventually':
        samples=[(1,1,0),(1,1,0),(1,1,int(not mutant)),(0,1,int(not mutant))]
        consequent='s_eventually response'
    else:
        samples=[(1,1,0),(1,int(not mutant),0),(1,1,1),(0,1,1)]
        consequent='hold '+operator+' response'
    expr='req '+('|=>' if nonoverlap else '|->')+' '+consequent
    passed,failed,pending=oracle(samples,operator,nonoverlap)
    code,result=replay(tmp_path,backend,expr,samples)
    expected='assert' if failed else 'error' if pending else 'pass'
    assert result.status==expected,result.to_dict()
    assert code==int(expected!='pass')
    checks={row['id']:row for row in result.extra['assertions']}
    assert (checks['a']['passed'],checks['a']['failed'],checks['a']['pending'])==(passed,failed,pending)
    assert (checks['c']['covered'],checks['c']['missed'],checks['c']['pending'])==(passed,failed,pending)
    if pending:
        assert result.extra['inconclusive']=='pending unbounded obligations'
    if expected=='pass':
        from rvw.cov.code import merge
        assert len(merge([str(tmp_path/'out')],root=tmp_path/'out')['points'])==2


@pytest.mark.parametrize('backend',['icarus','verilator'])
@pytest.mark.parametrize('operator',['until','until_with','s_until','s_until_with'])
def test_completion_sample_inclusion(tmp_path,backend,operator):
    _,result=replay(tmp_path,backend,'req |-> hold '+operator+' response',[(1,1,0),(0,0,1)])
    inclusive=operator.endswith('_with')
    assert result.status==('assert' if inclusive else 'pass'),result.to_dict()
    assert result.extra['assertions'][0]['failed']==int(inclusive)
    assert result.extra['assertions'][0]['passed']==int(not inclusive)


@pytest.mark.parametrize('backend',['icarus','verilator'])
def test_nonoverlap_final_request_remains_pending(tmp_path,backend):
    _,result=replay(tmp_path,backend,'req |=> s_eventually response',[(1,1,1)])
    assert result.status=='error'
    assert result.extra['assertions'][0]['pending']==1
    assert result.extra['assertions'][0]['passed']==0


@pytest.mark.parametrize('backend',['icarus','verilator'])
def test_native_sampled_activation(tmp_path,backend):
    _,result=replay(tmp_path,backend,'$rose(req) |-> s_eventually response',
                    [(0,1,0),(1,1,0),(1,1,1),(0,1,1)])
    assert result.status=='pass',result.to_dict()
    assert result.extra['assertions'][0]['passed']==1
    assert result.extra['assertions'][0]['pending']==0


@pytest.mark.parametrize('pending',[False,True])
def test_native_assumption_evidence(tmp_path,pending):
    samples=[(1,1,0),(0,1,0)] if pending else [(1,0,0),(0,1,1)]
    _,result=replay(tmp_path,'icarus','req |-> hold s_until response',samples,kind='assume')
    assert result.status=='error'
    assert result.extra['inconclusive']==('pending unbounded assumptions' if pending else 'stimulus violates a declared assumption')


@pytest.mark.parametrize('operator',['s_eventually','until'])
def test_native_unknown_response(tmp_path,operator):
    expr='req |-> '+('s_eventually response' if operator=='s_eventually' else 'hold until response')
    _,result=replay(tmp_path,'icarus',expr,[(1,1,0),(0,0,'x')])
    assert result.status==('error' if operator=='s_eventually' else 'assert'),result.to_dict()
    assert result.extra['assertions'][0]['pending']==int(operator=='s_eventually')


def test_native_bare_until(tmp_path):
    _,result=replay(tmp_path,'icarus','hold until response',[(0,1,1),(0,1,1)])
    assert result.status=='pass'
    assert result.extra['assertions'][0]['passed']==2



def test_pending_assumption_blocks_fault_verdict(tmp_path):
    if not all(shutil.which(tool) for tool in ('yosys','iverilog','vvp')):
        pytest.skip('Yosys and Icarus required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,req,response,output q); assign q=response; '
                      'f: assume property (@(posedge clk) req |-> s_eventually response); '
                      'a: assert property (@(posedge clk) 0); endmodule')
    events=tmp_path/'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1',events=[
        dict(time=0,inputs=dict(clk='0',req='1',response='0')),
        dict(time=1,inputs=dict(clk='1')),dict(time=2,inputs=dict(clk='0')),
        dict(time=3,inputs=dict(clk='1')),
    ])))
    out=tmp_path/'out'
    run(Namespace(verilog=[str(source)],top='m',events=str(events),out=str(out),
                  backend='icarus',observe=None,check_x=False,timeout=30))
    result=load_run(out)
    assert result.status=='error'
    assert result.extra['inconclusive']=='pending unbounded assumptions'
    assert next(p for p in result.extra['assertions'] if p['id']=='a')['failed']==2
