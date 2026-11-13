"""Semantic corpus also used to generate the published support table."""
import shutil
import subprocess

import pytest

from rvw.formal.temporal import Unsupported, lower, sequence

# A legal constant input and an independently selected bad constant input.
CASES = [
    ('first_match', 'first_match(1 ##[1:2] a) |-> b', 'a=1,b=1', 'a=1,b=0'),
    ('throughout', 'a throughout (1 ##2 b)', 'a=1,b=1', 'a=0,b=1'),
    ('within', 'a within (1 ##2 b)', 'a=1,b=1', 'a=0,b=1'),
    ('intersect', '(1 ##2 a) intersect (1 ##2 b)', 'a=1,b=1', 'a=1,b=0'),
    ('$past depth', '1 |-> 1 ##3 ($past(a,2) == a)', '[7:0] a=128', '[7:0] a=n'),
    ('$past nested', '1 |-> 1 ##3 ($past($past(a)) == a)', '[7:0] a=128', '[7:0] a=n'),
    ('$past signed', '1 |-> 1 ##3 ($past(a,2) < 0)', 'signed [7:0] a=-1', 'signed [7:0] a=1'),
    ('$past unsigned', '1 |-> 1 ##3 ($past(a,2) > 0)', '[7:0] a=128', '[7:0] a=0'),
    ('$past', '1 |=> $past(a) == a', '[7:0] a=128', '[7:0] a=n'),
    ('$rose', '1 |=> $rose(a)', '[7:0] a=n[0] ? 1 : 0', '[7:0] a=128'),
    ('$fell', '1 |=> $fell(a)', '[7:0] a=n[0] ? 0 : 1', '[7:0] a=1'),
    ('$stable', '1 |=> $stable(a)', '[7:0] a=128', '[7:0] a=n'),
    ('$changed', '1 |=> $changed(a)', '[7:0] a=n', '[7:0] a=128'),
]


def test_endpoint_paths():
    assert len(sequence('a within (1 ##2 b)')) == 3
    assert sequence('(a ##1 b) intersect c') == [('0',)]
    paths = sequence('a throughout (b ##1 c)')
    assert paths == [('(a) && (b)', '(a) && (c)')]
    assert len(sequence('(a ##[1:2] b) intersect (c ##2 d)')) == 1


@pytest.mark.parametrize('feature,expr,good,bad', CASES)
@pytest.mark.parametrize('mutant', [False, True])
def test_native(tmp_path, feature, expr, good, bad, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    # Only request edge checks on matching phases. The bad design keeps the
    # same request phase, so absence of a trigger cannot create a vacuous pass.
    if feature == '$rose':
        expr = 'n[0] |-> $rose(a)'
    elif feature == '$fell':
        expr = 'n[0] |-> $fell(a)'
    source = ('module m(input clk); reg [7:0] n=0; always @(posedge clk) n<=n+1; '
              'wire ' + (bad if mutant else good) + '; '
              'assert property (@(posedge clk) ' + expr + '); endmodule')
    rtl, _ = lower(source)
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
''')
    run = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                         capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), run.stdout


def test_sampled_guard():
    with pytest.raises(Unsupported):
        lower('module m; assert property (@(posedge clk) $past(a,0)); endmodule')


def test_support_table():
    from pathlib import Path
    rows = ['| Construct | Corpus | Scope |', '|---|---|---|']
    rows += [f'| `{feature}` | positive and negative native case | finite, single clock |'
             for feature, *_ in CASES]
    import ast
    module = ast.parse(Path('rvw/tests/formal/test_local_capture.py').read_text())
    features = ast.literal_eval(next(node.value for node in module.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES' for t in node.targets)))
    rows += [f'| `{feature}` | positive and negative native case | finite, single clock |' for feature in features]
    module = ast.parse(Path('rvw/tests/formal/test_unbounded_semantics.py').read_text())
    features = ast.literal_eval(next(node.value for node in module.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES' for t in node.targets)))
    native = ast.parse(Path('rvw/tests/formal/test_unbounded_native.py').read_text())
    pairs = ast.literal_eval(next(node.value for node in native.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'CASES' for t in node.targets)))
    assert features == [row[0] for row in pairs]
    rows += [f'| `{feature}` | positive and negative native case | infinite trace, single clock; `formal liveness` |'
             for feature in features]
    cross = ast.parse(Path('rvw/tests/formal/test_cross_clock.py').read_text())
    features = ast.literal_eval(next(node.value for node in cross.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'SUPPORT_FEATURES' for t in node.targets)))
    rows += [f'| `{feature.replace("|", "&#124;")}` | positive and negative native case | finite native timed replay; two clocks |'
             for feature in features]
    sampled_live = ast.parse(Path('rvw/tests/formal/test_live_sampled_native.py').read_text())
    functions = ast.literal_eval(next(node.value for node in sampled_live.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'FUNCTIONS' for t in node.targets)))
    rows += [f'| `liveness ${function}` | positive and negative native case | single-clock liveness; sampled history |'
             for function in functions]
    expected = '\n'.join(rows) + '\n'
    assert Path('rvw/src/rvw/formal/TEMPORAL_SUPPORT.md').read_text() == expected


def test_first_match_endpoints():
    from itertools import product
    paths = sequence('first_match(a ##[1:2] b)')
    # Independently enumerate the two possible endpoints. A later match must
    # disappear when the earlier endpoint succeeds.
    for a, b1, b2 in product((False, True), repeat=3):
        values = [{'a': a, 'b': False}, {'a': False, 'b': b1}, {'a': False, 'b': b2}]
        def atom(expr, row):
            expr = expr.replace('&&', ' and ').replace('!', ' not ')
            return bool(eval(expr, {'__builtins__': {}}, row))
        observed = {len(path)-1 for path in paths
                    if all(atom(expr, row) for expr, row in zip(path, values))}
        expected = {1} if a and b1 else {2} if a and b2 else set()
        assert observed == expected
