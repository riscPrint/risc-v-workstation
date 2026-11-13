import json
import shutil
from argparse import Namespace
import pytest
from rvw.formal.core_model import query
from rvw.formal.cores import prepare, run
from rvw.common.proc import run_group


def test_groups_and_initial_flags():
    text, bindings = query('(declare-sort |top_s| 0)', 'top', 3)
    _, assertions = prepare(text)
    assert set(assertions) == set(bindings['constraints'])
    assert '(not (|top_is| s1))' in text
    assert '(or (not (|top_a| s0)) (not (|top_a| s1)) (not (|top_a| s2)))' in text
    with pytest.raises(ValueError):
        query('', 'top', 0)


@pytest.mark.parametrize('bad,expected', [(False, 0), (True, 1)])
def test_native_captured_model(tmp_path, bad, expected):
    if not all(shutil.which(t) for t in ('yosys', 'z3')):
        pytest.skip('yosys and z3 required')
    root = tmp_path / 'run'
    (root / 'sby/model').mkdir(parents=True)
    rtl = tmp_path / 'top.v'
    rtl.write_text('module top(input a); always @* assert(' + ('a' if bad else "1'b1") + '); endmodule')
    il = root / 'sby/model/design.il'
    proc = run_group(['yosys', '-Q', '-T', '-p', f'read_verilog -formal {rtl}; prep -top top; write_rtlil {il}'], capture=True, timeout=10)
    assert proc.returncode == 0
    (root / 'result.json').write_text(json.dumps(dict(schema='rvw.formal/1', assertions=1, depth=3)))
    out = tmp_path / 'out'
    args = Namespace(result=str(root), depth=None, smt2=None, mapping=None, out=str(out), solver='z3', timeout=15, db=None, json=False)
    assert run(args) == expected
    report = json.loads((out / 'result.json').read_text())
    assert report['bounded_model']['depth'] == 3
    assert report['solver_status'] == ('sat' if bad else 'unsat')


def test_exact_property_selection():
    text = '; yosys-smt2-assert 0 first source\n; yosys-smt2-assert 1 second source\n'
    result, binding = query(text, 'top', 2, 'second')
    assert '(not (|top_a 1| s0))' in result
    assert binding['property_id'] == 'top:second'
    with pytest.raises(ValueError, match='missing'):
        query(text, 'top', 2, 'unknown')


def test_native_conflicting_environment(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'z3')):
        pytest.skip('yosys and z3 required')
    root = tmp_path / 'run'
    (root / 'sby/model').mkdir(parents=True)
    rtl = tmp_path / 'top.v'
    rtl.write_text('module top(input a); always @* begin assume(a); assume(!a); assert(a); end endmodule')
    il = root / 'sby/model/design.il'
    proc = run_group(['yosys', '-Q', '-T', '-p', f'read_verilog -formal {rtl}; prep -top top; write_rtlil {il}'], capture=True, timeout=10)
    assert proc.returncode == 0
    (root / 'result.json').write_text(json.dumps(dict(schema='rvw.formal/1', assertions=1, depth=3)))
    out = tmp_path / 'out'
    assert run(Namespace(result=str(root), depth=None, smt2=None, mapping=None, out=str(out),
                         solver='z3', timeout=15, db=None, json=False)) == 1
    report = json.loads((out / 'result.json').read_text())
    assert report['status'] == 'inconclusive' and report['environment_core']
    assert report['bounded_model']['feasibility'] == 'unsat'


def test_assumptions_group_all_samples_by_captured_cell():
    model = '; yosys-smt2-assume 0 guard source\n; yosys-smt2-assume 1 unused source\n'
    text, binding = query(model, 'top', 2)
    assert '(and (|top_u 0| s0) (|top_u 0| s1))' in text
    assert binding['constraints']['assumption_0']['cell'] == 'guard'
    assert 'assumptions_0' not in binding['constraints']
