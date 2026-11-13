"""Native checks for literal X/Z propagation in Boolean C translation."""
import itertools
import json
import shutil
import subprocess

import pytest
from rvw.cli import main
from rvw.formal.bitc import GATES, uncertainty, translate

TOOLS = all(shutil.which(t) for t in ('yosys', 'cbmc'))


@pytest.mark.skipif(not shutil.which('cc'), reason='needs a C compiler')
def test_gate_uncertainty_matches_enumeration(tmp_path):
    source = ['#include <stdio.h>', 'int main(void) {']
    expected = []
    def gate(kind, a, b, s):
        return {'$_BUF_': a, '$_NOT_': not a, '$_AND_': a and b,
                '$_NAND_': not (a and b), '$_OR_': a or b,
                '$_NOR_': not (a or b), '$_XOR_': a != b,
                '$_XNOR_': a == b, '$_MUX_': b if s else a}[kind]
    for kind in sorted(GATES):
        count = 1 if kind in ('$_BUF_', '$_NOT_') else (3 if kind == '$_MUX_' else 2)
        expression = uncertainty(kind, ['a', 'b', 's'][:count], ['ta', 'tb', 'ts'][:count])
        for values in itertools.product((0, 1), repeat=count):
            for unknown in itertools.product((0, 1), repeat=count):
                possibilities = [((0, 1) if t else (v,)) for v, t in zip(values, unknown)]
                outputs = {gate(kind, *(x+(0,)*(3-count))) for x in itertools.product(*possibilities)}
                expected.append(int(len(outputs) > 1))
                declarations = ','.join(f'{name}={value}' for name, value in
                    zip(['a', 'b', 's'][:count]+['ta', 'tb', 'ts'][:count], values+unknown))
                source.append('{ int '+declarations+'; printf("%d\\n", '+expression+'); }')
    source.append('}')
    c = tmp_path/'gates.c'; c.write_text('\n'.join(source))
    exe = tmp_path/'gates'
    subprocess.run(['cc', str(c), '-o', str(exe)], check=True, capture_output=True)
    actual = subprocess.run([str(exe)], check=True, text=True, capture_output=True).stdout
    assert list(map(int, actual.split())) == expected


@pytest.mark.skipif(not TOOLS, reason='needs Yosys and CBMC')
@pytest.mark.parametrize('expression,status', [
    ("8'bx & 8'b0", 'proved'),
    ("a[0] ? (a & 8'hfe) : (a & 8'hfe)", 'proved'),
    ("a[0] ? 8'bx : (a & 8'hfe)", 'inconclusive'),
    ("8'bz", 'inconclusive'),
])
def test_literal_definedness(tmp_path, expression, status):
    rtl=tmp_path/'dut.v'; rtl.write_text('module dut(input [7:0] a,b,output [7:0] y); assign y='+expression+'; endmodule')
    ref=tmp_path/'ref.c'; ref.write_text('uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags){return '+('0' if '8\'b0' in expression else '(a & 254)')+';}')
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(ref),'--width','8','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==status, result
    assert result['rtl_definedness']==('proved' if status=='proved' else 'inconclusive')


@pytest.mark.skipif(not TOOLS, reason='needs Yosys and CBMC')
@pytest.mark.parametrize('observed,mode', [('flags','comb'),('done','fixed'),('done','bounded'),('y','fixed')])
def test_unknown_flags_and_state_never_become_counterexamples(tmp_path, observed, mode):
    sequential=mode!='comb'
    header='input clk,reset,start,output done,' if sequential else ''
    body='assign done='+ ("1'bx" if observed=='done' else 'start')+';' if sequential else ''
    if observed=='y':
        body+="reg [7:0] q; always @(posedge clk) q <= reset ? 8'bx : q; assign y=q;"
    else:
        body+='assign y=a;'
    rtl=tmp_path/'dut.v';rtl.write_text('module dut('+header+'input [7:0] a,b,output [7:0] y,output [4:0] flags);'+body+
        "assign flags="+("5'bx" if observed=='flags' else "5'b0")+';endmodule')
    ref=tmp_path/'ref.c';ref.write_text('uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags){return a;}')
    out=tmp_path/'out'
    extra=[] if not sequential else ['--latency' if mode=='fixed' else '--max-latency','1']
    main(['formal','datapath','--rtl',str(rtl),'--model',str(ref),'--width','8',*extra,'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='inconclusive' and result['rtl_definedness']=='inconclusive', result


def test_default_translator_still_rejects_literal_unknown():
    design={'modules':{'dut':{'ports':{'a':{'direction':'input','bits':list(range(2,10))},
        'b':{'direction':'input','bits':list(range(10,18))},'y':{'direction':'output','bits':['x']*8}},
        'cells':{},'netnames':{}}}}
    code,ports,put,get=translate(design,8,0)
    with pytest.raises(ValueError,match='X/Z'):
        get('y')
