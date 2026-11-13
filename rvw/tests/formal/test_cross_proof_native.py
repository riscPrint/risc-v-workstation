from argparse import Namespace
import json
import random
import shutil
import subprocess

import pytest

from rvw.formal.cross_proof import prepare, monitor, run


@pytest.mark.parametrize('overlap', [False,True])
def test_native_monitor_matches_preupdate_oracle(tmp_path,overlap):
    if not all(shutil.which(t) for t in ('iverilog','vvp')):
        pytest.skip('Icarus required')
    _,row=prepare('module m(input a,b,req,ack); p: assert property (@(posedge a) req '+
                  ('|->' if overlap else '|=>')+' @(posedge b) ack); endmodule','m')
    rng=random.Random(46)
    samples=[(0,0,0,0)]+[tuple(rng.randrange(2) for _ in range(4)) for _ in range(100)]
    previous=(0,0,0,0)
    pending=False
    expected=[]
    for index,current in enumerate(samples):
        a,b,_,_=current
        pa,pb,req,ack=previous
        born=index>0 and a and not pa and req
        target=index>0 and b and not pb
        if target and (pending or overlap and born):
            expected.append(str(ack))
        pending=(False if overlap else born) if target else pending or born
        previous=current
    code=['module tb; reg step=0,a=0,b=0,req=0,ack=0;',monitor(row,'posedge step',simulation=True),'initial begin']
    for a,b,req,ack in samples:
        code += [f'a={a}; b={b}; req={req}; ack={ack}; #1; step=1; #1; step=0;']
    code += ['$finish; end endmodule']
    (tmp_path/'m.sv').write_text('\n'.join(code))
    compiled=subprocess.run(['nice','-n','10','iverilog','-g2012','-s','tb','-o',str(tmp_path/'sim'),str(tmp_path/'m.sv')],capture_output=True,text=True,timeout=30)
    assert compiled.returncode==0,compiled.stderr
    result=subprocess.run(['nice','-n','10','vvp',str(tmp_path/'sim')],capture_output=True,text=True,check=True,timeout=30)
    actual=[line.split()[1] for line in result.stdout.splitlines() if line.startswith('CHECK ')]
    assert actual==expected


@pytest.mark.parametrize('edge',['posedge','negedge'])
@pytest.mark.parametrize('overlap',[False,True])
@pytest.mark.parametrize('mutant',[False,True])
def test_native_global_clock_proof_and_refutation(tmp_path,overlap,mutant,edge):
    if not all(shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('Yosys, SBY and Yices required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input a,b,req); wire ack='+('0' if mutant else '1')+'; '
        'p: assert property (@(posedge a) req '+ ('|->' if overlap else '|=>')+
        ' @('+edge+' b) ack); endmodule')
    out=tmp_path/'out'
    run(Namespace(source=str(source),top='m',out=str(out),depth=12,timeout=30,
                  mode='prove',engine='smtbmc:yices',proof_cache=None))
    result=json.loads((out/'proof/results.json').read_text())['tests'][0]
    assert result['formal_status']==('failed' if mutant else 'proven'),result
    assert result['activation']['status']=='reached',result
    assert (out/'proof/junit.xml').exists()


def test_sequential_destination_uses_value_before_edge(tmp_path):
    if not all(shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('Yosys, SBY and Yices required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input a,b,req); reg ack=1; always @(posedge b) ack<=0; '
        'p: assert property (@(posedge a) req |-> @(posedge b) !ack); endmodule')
    out=tmp_path/'out'
    run(Namespace(source=str(source),top='m',out=str(out),depth=12,timeout=30,
                  mode='bmc',engine='smtbmc:yices',proof_cache=None))
    result=json.loads((out/'proof/results.json').read_text())['tests'][0]
    # !ack becomes true after the first destination edge. The assertion must
    # see its false pre-edge value, so a request before that edge refutes it.
    assert result['formal_status']=='failed',result
