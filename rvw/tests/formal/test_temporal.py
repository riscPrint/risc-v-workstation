import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from rvw.formal.temporal import Unsupported, lower, sequence


def test_paths():
    assert sequence('##1 b') == [('1', 'b')]
    assert sequence('a ##[1:2] b') == [('a', 'b'), ('a', '1', 'b')]
    assert sequence('(a ##1 b)[*2]') == [('a', 'b', 'a', 'b')]
    assert sequence('a ##0 b') == [('(a) && (b)',)]
    assert sequence('a or b') == [('a',), ('b',)]


@pytest.mark.parametrize('expression,diagnostic', [
    ('a ##[1:$] b', 'unbounded_range'), ('a[*0:2]', 'empty_repetition'),
    ('a[->2]', 'sequence_operator'), ('s_eventually a', 's_eventually'),
    ('a throughout b', 'throughout'), ('$past(a)', 'sampled_function'),
    ('a ##100 b', 'range_limit')])
def test_unsupported(expression, diagnostic):
    with pytest.raises(Unsupported, match=f'unsupported:{diagnostic}'):
        sequence(expression)


def test_named_and_no_drop():
    source = '''module m(input clk, a, b);
    sequence s; a ##1 b; endsequence
    p: assert property (@(posedge clk) s |=> b);
    endmodule'''
    rtl, props = lower(source)
    assert props[0]['id'] == 'p'
    assert props[0]['horizon'] == 2
    assert 'assert (' in rtl
    assert 'endsequence' not in rtl
    with pytest.raises(Unsupported, match='unsupported:property'):
        lower('module m; property unused; 1; endproperty endmodule')
    with pytest.raises(Unsupported, match='unsupported:recursive_sequence'):
        lower('module m; sequence s; s; endsequence endmodule')


# Each native test has a legal design and a seeded RTL fault. No optional
# frontend plugin is needed: the generated monitors use native Yosys Verilog.
CASES = [
    ('a |-> b', 'wire b = a;', 'wire b = !a;'),
    ('a |=> b', 'reg b = 0; always @(posedge clk) b <= a;', 'wire b = !a;'),
    ('a ##1 b |-> b', 'reg b=0; always @(posedge clk) b<=a;', 'wire b=0;'),
    ('a |-> a ##[1:3] b', 'reg b=0; always @(posedge clk) b<=a;', 'wire b=0;'),
    ('a |-> a[*2]', 'wire a=1;', 'reg a=1; always @(posedge clk) a<=!a;'),
    ('a |-> a ##0 b', 'wire b=a;', 'wire b=!a;'),
    ('a |-> (b or c)', 'wire b=1,c=0;', 'wire b=0,c=0;'),
]


@pytest.mark.parametrize('engine', ['smtbmc yices', 'abc bmc3'])
@pytest.mark.parametrize('index', range(len(CASES)))
@pytest.mark.parametrize('mutant', [False, True])
def test_native(tmp_path, index, mutant, engine):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    prop, good, bad = CASES[index]
    design = bad if mutant else good
    if index != 4:
        design = 'wire a=1; ' + design
    # Make the sequence-antecedent mutant fail at its endpoint, rather than
    # remove the antecedent and create a vacuous pass.
    if index == 2:
        design = 'wire a=1; wire b=1; wire c=' + ('0;' if mutant else '1;')
        prop = 'a ##1 b |-> c'
    rtl, _ = lower(f'module m(input clk); {design} assert property (@(posedge clk) {prop}); endmodule')
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 10
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
'''.replace('smtbmc yices', engine))
    run = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                         capture_output=True, text=True, timeout=30)
    status = (tmp_path / 'job' / 'status').read_text().split()[0]
    expected = 'FAIL' if mutant else 'PASS'
    if engine == 'abc bmc3' and not mutant and index in (0, 2, 4, 5, 6):
        # ABC refuses a fixture optimized to a combinational network.
        expected = 'ERROR'
        assert 'Does not work for combinational networks' in run.stdout
    assert status == expected, run.stdout + run.stderr


def test_disable_and_kinds():
    rtl, rows = lower('''module m(input clk, rst, a);
    assume property (@(posedge clk) disable iff(rst) a |=> a);
    cover property (@(posedge clk) a ##1 a);
    endmodule''')
    assert [r['kind'] for r in rows] == ['assume', 'cover']
    assert 'or posedge rvw_sva_0_0_cancel' in rtl
    assert 'if (rvw_sva_0_0_cancel)' in rtl


@pytest.mark.parametrize('kind', ['assert', 'assume', 'cover'])
@pytest.mark.parametrize('mutant', [False, True])
def test_native_disable_and_kinds(tmp_path, kind, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    # A request is followed by reset, which cancels the unfinished attempt.
    # Without disable iff the seeded zero response must fail.
    disable = '' if mutant else 'disable iff (rst) '
    if kind == 'assert':
        design = '''reg [2:0] n=0; always @(posedge clk) n<=n+1;
          wire a=n==0; wire rst=n==1; wire b=0;'''
        prop = f'{disable}a |-> a ##2 b'
    elif kind == 'assume':
        design = 'wire rst=0; wire a; wire b;'
        prop = 'a |=> b'
    else:
        design = 'wire rst=0; wire a=1; wire b=' + ('0;' if mutant else '1;')
        prop = 'a ##[1:2] b'
    source = f'module m(input clk); {design} {kind} property (@(posedge clk) {prop});'
    if kind == 'assume':
        source += f' assert property (@(posedge clk) a |=> {"!b" if mutant else "b"});'
    source += ' endmodule'
    rtl, _ = lower(source)
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text(f'''[options]
mode {'cover' if kind == 'cover' else 'bmc'}
depth 12
multiclock on
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    result = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), result.stdout


def test_native_bmc_frontend(tmp_path):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    import sys
    source = tmp_path / 'm.sv'
    source.write_text('''module m(input clk, a); reg b=0;
      always @(posedge clk) b<=a;
      assert property (@(posedge clk) a |=> b); endmodule''')
    result = subprocess.run(['nice', '-n', '10', sys.executable, '-m', 'rvw', 'formal', 'bmc',
                             '--frontend', 'temporal', '--verilog', str(source), '--top', 'm',
                             '--depth', '6', '--out', str(tmp_path / 'out')],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / 'out/result.json').read_text())
    assert data['frontend'] == 'temporal'
    assert data['temporal_properties'][0]['horizon'] == 1
    assert data['status'] == 'pass'


@pytest.mark.parametrize('mutant', [False, True])
def test_native_vector_boolean(tmp_path, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    # A vector atom is true when any bit is set, not only bit zero.
    rtl, _ = lower("module m(input clk); wire [1:0] bus=2'b10; "
                   + 'assert property (@(posedge clk) bus |-> ' + ('0' if mutant else '1') + '); endmodule')
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 4
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    result = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), result.stdout
