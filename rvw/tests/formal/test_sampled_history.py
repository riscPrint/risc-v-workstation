import shutil
import subprocess

import pytest

from rvw.formal.sampled import emit, validate
from rvw.formal.temporal import Unsupported


@pytest.mark.parametrize('expression', ['$past(a,0)', '$past(a,-1)', '$past(a,65)', '$past(a,n)',
                                       '$past(a,2,enable)', '$rose(a,clk)', '$unknown(a)'])
def test_refusals(expression):
    with pytest.raises(ValueError):
        validate(expression)


def test_register_depth():
    _, lines = emit('$past(a,3)', 'clk', 'sample')
    assert sum(line.startswith('reg ') for line in lines) == 3
    _, lines = emit('$past($past(a))', 'clk', 'sample')
    assert sum(line.startswith('reg ') for line in lines) == 2


def test_native_four_state(tmp_path):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus required')
    values = ['xxxx','0001','xxxx','zzzz','zzzz','0000','1001']
    lines, expressions = ['module m; reg clk=0; reg [3:0] a;'], []
    for name in ('rose','fell','stable','changed'):
        expression, declarations = emit('$'+name+'(a)', 'clk', name)
        lines.extend(declarations)
        expressions.append(expression)
    lines += ['always @(posedge clk) $display("VALUES %b %b %b %b", '+', '.join(expressions)+');',
              'initial begin']
    for value in values:
        lines += [f"a=4'b{value}; #1; clk=1; #1; clk=0; #1;"]
    lines += ['$finish; end endmodule']
    (tmp_path / 'm.sv').write_text('\n'.join(lines))
    compile_ = subprocess.run(['nice','-n','10','iverilog','-g2012','-s','m','-o','m.vvp','m.sv'],
                              cwd=tmp_path,capture_output=True,text=True,timeout=20)
    assert compile_.returncode == 0, compile_.stderr
    result = subprocess.run(['nice','-n','10','vvp','m.vvp'],cwd=tmp_path,capture_output=True,text=True,timeout=20)
    observed = [line.split()[1:] for line in result.stdout.splitlines() if line.startswith('VALUES ')]
    previous, expected = 'xxxx', []
    for value in values:
        expected.append([str(int(value[-1]=='1' and previous[-1]!='1')),
                         str(int(value[-1]=='0' and previous[-1]!='0')),
                         str(int(value==previous)),str(int(value!=previous))])
        previous = value
    assert observed == expected
