from argparse import Namespace
import json
import random
import re
import shutil
import subprocess

import pytest

from rvw.formal.liveness import lower_live,run


@pytest.mark.parametrize('operator',['->','='])
@pytest.mark.parametrize('mutant',[False,True])
def test_native_range_choice_engine(tmp_path,operator,mutant):
    if not all(shutil.which(tool) for tool in ('yosys','sby','yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,reset); reg [1:0] n=0; '
                      'always @(posedge clk) if(reset)n<=0; else n<=n+1; '
                      'wire req=!reset && n==0; wire b=n<2; wire c='+('0' if mutant else 'n==2')+'; '
                      'assert property (@(posedge clk) req |-> strong(b['+operator+'1:2] ##1 c)); endmodule')
    out=tmp_path/'proof'
    run(Namespace(source=str(source),top='m',out=str(out),run=True,timeout=30,
                  backend='l2s',reset='reset',engine='abc:pdr',mode='prove',depth=12))
    result=json.loads((out/'result.json').read_text())
    assert result['observation']==('FAIL' if mutant else 'PASS'),result


def accepts(prefix,loop,minimum,maximum,operator):
    # Language oracle: each request needs one permitted number of occurrences
    # and a completion at its legal endpoint. This does not use monitor states.
    trace=prefix+loop*(maximum+4)
    for start,(req,_,_) in enumerate(prefix+loop):
        if not req:
            continue
        occurrences=[i for i in range(start,len(trace)) if trace[i][1]]
        accepted=False
        for count in range(minimum,maximum+1):
            if len(occurrences)<count:
                continue
            event=occurrences[count-1]
            if operator=='->':
                accepted |= event+1<len(trace) and trace[event+1][2]
            else:
                next_event=occurrences[count] if len(occurrences)>count else len(trace)-1
                accepted |= any(trace[i][2] for i in range(event+1,next_event+1))
        if not accepted:
            return False
    return True


def test_emitted_automata_against_lasso_language_oracle(tmp_path):
    if not all(shutil.which(tool) for tool in ('iverilog','vvp')):
        pytest.skip('Icarus required')
    variants=[('->',1,2),('=',1,2),('->',2,3),('=',2,3)]
    properties='\n'.join(f'assert property (@(posedge clk) req |-> strong(b[{op}{lo}:{hi}] ##1 c));'
                         for op,lo,hi in variants)
    rtl,rows,_=lower_live('module m(input clk,req,b,c);'+properties+' endmodule','m')
    rng=random.Random(7321)
    traces=[([],[(True,True,True)]),([],[(True,False,True)]),([],[(True,True,False)]),
            ([(True,True,False)],[(False,False,True)]),
            ([],[(True,True,False),(False,True,False),(False,False,False),(False,False,True)])]
    traces += [([tuple(bool(rng.getrandbits(1)) for _ in range(3)) for _ in range(rng.randrange(3))],
                [tuple(bool(rng.getrandbits(1)) for _ in range(3)) for _ in range(rng.randrange(1,4))])
               for _ in range(64)]
    registers=re.findall(r'\breg\s*(?:\[[^\]]+\]\s*)?(rvw_live_\w+)\s*=',rtl)
    bench=['module tb; reg clk=0,req=0,b=0,c=0; m dut(clk,req,b,c); initial begin']
    refs=', '.join('dut.'+row['wire'] for row in rows)
    for index,(prefix,loop) in enumerate(traces):
        bench += [f'dut.{name}=0;' for name in registers]
        bench.append(f'$display("CASE {index}");')
        for req,b,c in prefix+loop*16:
            bench.append(f'req={int(req)}; b={int(b)}; c={int(c)}; #1; clk=1; #1; '
                         f'$display("%b%b%b%b",{refs}); clk=0; #1;')
    bench += ['$finish; end endmodule']
    (tmp_path/'m.sv').write_text(rtl+'\n'+'\n'.join(bench))
    compiled=subprocess.run(['nice','-n','10','iverilog','-g2012','-s','tb','-o','sim','m.sv'],
                            cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert compiled.returncode==0,compiled.stderr
    result=subprocess.run(['nice','-n','10','vvp','sim'],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    parts=re.split(r'CASE (\d+)\n',result.stdout)[1:]
    for index,output in zip(parts[::2],parts[1::2]):
        prefix,loop=traces[int(index)]
        samples=[line for line in output.splitlines() if re.fullmatch('[01xz]{4}',line)][-8*len(loop):]
        assert len(samples)==8*len(loop)
        for i,(op,lo,hi) in enumerate(variants):
            observed=any(sample[i]=='1' for sample in samples)
            assert observed==accepts(prefix,loop,lo,hi,op),(index,op,lo,hi,prefix,loop,samples)
