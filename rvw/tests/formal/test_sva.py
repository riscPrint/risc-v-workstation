"""Qualified clocked SVA syntax and native positive/negative semantics."""
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from rvw.common.proc import run_group
from rvw.formal.sva import validate_sources
from rvw.formal.slang_capability import sva_unavailable


@pytest.mark.parametrize('body', [
    'a |-> b |=> a', 'a |=> b', '(a |-> b)', 'a ##1 b', 'a[*2]', '$past(a, 2)',
    'strong(a)', '@(negedge clk) a', 'a until b', 'a and b',
])
def test_refuse_unqualified_constructs(tmp_path, body):
    source = tmp_path / 'bad.sv'
    source.write_text(f'module top(input clk,a,b); assert property (@(posedge clk) {body}); endmodule')
    # Repetition is rejected by the native frontend before SBY, too. Refuse it locally.
    with pytest.raises(ValueError, match='unsupported SVA'):
        validate_sources([source], 'clk')


@pytest.mark.parametrize('extra', ['`define P a', 'property p; a; endproperty',
                                  'default clocking cb @(posedge clk); endclocking',
                                  'assert(a);', 'cover property (@(posedge clk) a);'])
def test_refuse_other_property_forms(tmp_path, extra):
    source = tmp_path / 'bad.sv'
    source.write_text('module top(input clk,a); ' + extra + ' endmodule')
    with pytest.raises(ValueError, match='unsupported SVA'):
        validate_sources([source], 'clk')


CASES = {
    'boolean': ('q == expected', 'q != expected'),
    'disable': ('disable iff (reset) q == expected', 'disable iff (reset) q != expected'),
    'past': ('!valid || q == $past(a)', '!valid || q != $past(a)'),
    'rose': ('!valid || $rose(a) == (a[0] && !prev[0])', '!valid || $rose(a) != (a[0] && !prev[0])'),
    'fell': ('!valid || $fell(a) == (!a[0] && prev[0])', '!valid || $fell(a) != (!a[0] && prev[0])'),
    'stable': ('!valid || $stable(a) == (a == prev)', '!valid || $stable(a) != (a == prev)'),
    'changed': ('!valid || $changed(a) == (a != prev)', '!valid || $changed(a) != (a != prev)'),
    'assume': ('a == 2', 'a != 2'),
    'overlap': ('a == 2 |-> a[1]', 'a == 2 |-> !a[1]'),
    'overlap_assume': ('!a[0] || a[1]', 'a[0] && !a[1]'),
    'overlap_disable': ('disable iff (reset) a == 2 |-> a[1]',
                        'disable iff (reset) a == 2 |-> !a[1]'),
}


@pytest.mark.parametrize('construct', CASES)
@pytest.mark.parametrize('negative', [False, True], ids=['pass', 'fail'])
@pytest.mark.parametrize('engine', ['smtbmc:yices', 'abc:bmc3'])
def test_native_semantics(tmp_path, construct, negative, engine):
    if not os.environ.get('RVW_SLANG') or not shutil.which('sby'):
        pytest.skip('native tests need RVW_SLANG, Yosys, SBY and solvers')
    reason = sva_unavailable(os.environ['RVW_SLANG'])
    if reason:
        pytest.skip(reason)
    source = tmp_path / 'top.sv'
    expr = CASES[construct][negative]
    body = f'count != 3 || ({expr})' if negative else f'count < 7 && ({expr})'
    if construct in ('overlap', 'overlap_disable'):
        body = expr
    if construct == 'disable':
        expr = CASES['boolean'][negative]
        body = 'disable iff (reset) ' + (f'count != 3 || ({expr})' if negative else f'count < 7 && ({expr})')
    # q is the prior input. expected is independent reference state.
    source.write_text('''module top(input clk, reset, input [1:0] a);
reg [1:0] q = 0, expected = 0, prev = 0;
reg valid = 0;
reg [3:0] count = 0;
always @(posedge clk) begin
  q <= a; expected <= a; prev <= a; valid <= 1; count <= count + 1;
end
''' + ('assume property (@(posedge clk) a == 2);\n' if construct == 'assume' else
        'assume property (@(posedge clk) a[0] |-> a[1]);\n' if construct == 'overlap_assume' else '') +
        f'assert property (@(posedge clk) {body});\nendmodule\n')
    if construct == 'disable':
        source.write_text(source.read_text().replace('expected = 0', 'expected = 1'))
    out = tmp_path / 'proof'
    result = run_group([sys.executable, '-m', 'rvw', 'formal', 'bmc', '--frontend', 'slang',
                        '--verilog', str(source), '--top', 'top', '--depth', '6',
                        '--engine', engine, '--timeout', '45', '--out', str(out)],
                       capture=True, timeout=100)
    assert result.returncode == int(negative), result.stdout + result.stderr
    data = json.loads((out / 'result.json').read_text())
    assert data['status'] == ('fail' if negative else 'pass')
    assert data['frontend'] == 'slang'
    assert data['assertions'] == 1


@pytest.mark.parametrize('body', ['a |=> a |-> a', 'a ##1 a', 'a[*2]', '@(negedge clk) a'])
def test_native_refusal_before_sby(tmp_path, body):
    source = tmp_path / 'bad.sv'
    source.write_text(f'module top(input clk,a); assert property (@(posedge clk) {body}); endmodule')
    out = tmp_path / 'proof'
    result = run_group([sys.executable, '-m', 'rvw', 'formal', 'bmc', '--frontend', 'slang',
                        '--verilog', str(source), '--top', 'top', '--out', str(out)],
                       capture=True, timeout=10)
    assert result.returncode == 2
    assert 'unsupported SVA' in result.stderr
    assert not (out / 'sby').exists()
    assert not (out / 'result.json').exists()


def test_slang_dependency_report_is_required_and_closed(tmp_path):
    from argparse import Namespace
    from rvw.formal.snapshot import InputSnapshot
    source = tmp_path / 'top.sv'
    source.write_text('module top(input clk,a); assert property (@(posedge clk) a); endmodule')
    out = tmp_path / 'out'
    out.mkdir()
    snapshot = InputSnapshot(Namespace(verilog=[str(source)], checks=None,
                                       frontend='slang', clock='clk', engine='smtbmc:yices'), out)
    with pytest.raises(SystemExit):
        snapshot.check_frontend()
    dependency = out / 'slang.d'
    dependency.write_text(str(snapshot.sources[0].relative_to(out)) + '\n')
    snapshot.check_frontend()
    dependency.write_text(dependency.read_text() + '/outside/hidden.sv\n')
    with pytest.raises(SystemExit):
        snapshot.check_frontend()


@pytest.mark.parametrize('expr', ['a |-> b', '(a && b) |-> $past(a)',
                                  'disable iff (reset) a |-> b'])
def test_accept_simple_implication_syntax(tmp_path, expr):
    source = tmp_path / 'top.sv'
    source.write_text('module top(input clk,reset,a,b); assert property (@(posedge clk) ' + expr + '); endmodule')
    validate_sources([source], 'clk')


@pytest.mark.parametrize('body,accepted', [
    ('a |-> b', True), ('a |=> b', False),
    ('a[*2] |-> b', False), ('a |-> b[*2]', False),
    ('(a |-> b) |-> a', False),
])
def test_native_frontend_boundary_without_local_guard(tmp_path, body, accepted):
    plugin = os.environ.get('RVW_SLANG')
    if not plugin or not shutil.which('yosys'):
        pytest.skip('needs source-built native slang')
    reason = sva_unavailable(plugin)
    if reason:
        pytest.skip(reason)
    source = tmp_path / 'top.sv'
    source.write_text(f'module top(input clk,a,b); assert property (@(posedge clk) {body}); endmodule')
    result = run_group(['yosys', '-Q', '-T', '-m', plugin, '-p', f'read_slang --top top {source}'],
                       capture=True, timeout=15)
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
