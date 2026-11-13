import shutil
import subprocess

import pytest

from rvw.formal.temporal import Unsupported, lower


SUPPORT_FEATURES = ['local variables']


def property_source(declaration, expression):
    return f'property response; {declaration} @(posedge clk) {expression}; endproperty p: assert property(response);'


def test_typed_metadata():
    _, rows = lower('module m; ' + property_source('int signed v; logic [3:0] tag;',
                     '(req,v=data,tag=kind) |=> (out==v && out_tag==tag)') + 'endmodule')
    assert rows[0]['local_variables'] == dict(v=dict(width=32,signed=True),tag=dict(width=4,signed=False))


@pytest.mark.parametrize('declaration,expression,diagnostic', [
    ('logic v;', 'req |=> v', 'local_capture_antecedent'),
    ('logic v;', '(req,v=data) |=> $past(v)', 'local_sampled_use'),
    ('logic [7:0] v;', '(req,v=data) |=> v[0]', 'local_select'),
    ('int v;', '(req,v=data,v=v+1) |=> out==v', 'local_reassignment'),
    ('int v,w;', '(req,v=data,w=v) |=> out==w', 'local_reassignment'),
    ('bit v;', '(req,v=data) |=> out==v', 'local_declaration'),
    ('logic v;', 'disable iff(v) (req,v=data) |=> out==v', 'local_disable'),
])
def test_refusals(declaration, expression, diagnostic):
    with pytest.raises(Unsupported, match=diagnostic):
        lower('module m; '+property_source(declaration,expression)+' endmodule')


@pytest.mark.parametrize('mutant', [False,True])
@pytest.mark.parametrize('delay', [1,2,3])
def test_native_overlapping_attempts(tmp_path, delay, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    # Every cycle starts another capture with different data. A shared capture
    # register would overwrite earlier attempts and fail the legal fixture.
    design = ['module m(input clk); reg [7:0] data=0; always @(posedge clk) data<=data+1;',
              'wire req=1;']
    previous = 'data'
    for i in range(delay):
        design += [f'reg [7:0] d{i}=0; always @(posedge clk) d{i}<={previous};']
        previous = f'd{i}'
    expression = f'(req,v=data) |-> 1 ##{delay} ({previous} == v' + ('+1)' if mutant else ')')
    design += [property_source('logic [7:0] v;',expression),'endmodule']
    _native(tmp_path,'\n'.join(design),mutant)


@pytest.mark.parametrize('mutant', [False,True])
def test_native_signed_capture(tmp_path, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    source = 'module m(input clk); wire req=1; wire signed [7:0] data=' + ('1;' if mutant else '-1;')
    source += property_source('int v;', '(req,v=data) |=> v<0') + 'endmodule'
    _native(tmp_path,source,mutant)


def _native(tmp_path, source, mutant):
    rtl, _ = lower(source)
    (tmp_path/'m.sv').write_text(rtl)
    (tmp_path/'job.sby').write_text('''[options]
mode bmc
depth 12
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    run = subprocess.run(['nice','-n','10','sby','-f','job.sby'],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert (tmp_path/'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), run.stdout


def test_native_adjacent_endmodule(tmp_path):
    if not shutil.which('yosys'):
        pytest.skip('Yosys required')
    source, _ = lower('module m(input clk);assert property(@(posedge clk) 1);endmodule')
    (tmp_path/'m.sv').write_text(source)
    result = subprocess.run(['nice','-n','10','yosys','-Q','-p','read_verilog -sv -formal m.sv; prep -top m'],
                            cwd=tmp_path,capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
