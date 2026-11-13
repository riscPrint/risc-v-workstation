import shutil
import subprocess

import pytest

from rvw.formal.psl import translate
from rvw.formal.temporal import Unsupported, lower


@pytest.mark.parametrize('body,expected', [
    ('assert always a;', 'a'),
    ('assert always a -> b;', 'a |-> b'),
    ('assert always a -> next b;', 'a |-> 1 ##1 b'),
    ('assert always a -> next[2] (b);', 'a |-> 1 ##2 b'),
    ('assert always {a;b} |-> {c;d};', 'a ##1 b |-> c ##1 d'),
    ('assume always {a} |=> {b[*1 to 3]};', 'a |=> b[*1:3]'),
    ('cover {a;b};', 'a ##1 b'),
])
def test_subset(body, expected):
    output = translate('default clock = (posedge clk); ' + body)
    assert expected in output
    assert lower('module m;\n' + output + 'endmodule')[1]


@pytest.mark.parametrize('source', [
    'assert a;', 'assert always a -> eventually! b;',
    'assert always {a[+]};', 'assert always {a[*]};',
    'default clock = (posedge clk); default clock = (posedge clk); assert always a;',
    'assert always a', 'assert always {a;{b;c}};',
])
def test_refuse(source):
    with pytest.raises(ValueError):
        translate(source, 'clk')


@pytest.mark.parametrize('mutant', [False, True])
@pytest.mark.parametrize('body', ['assert always a -> next b;', 'assert always {a} |=> {b};'])
def test_native(tmp_path, mutant, body):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    sva = translate(body, 'clk')
    source = 'module m(input clk); wire a=1; wire b=' + ('0;' if mutant else '1;')
    rtl, _ = lower(source + sva + 'endmodule')
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 8
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    run = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                         capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), run.stdout
