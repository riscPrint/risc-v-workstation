import json
import shutil
from argparse import Namespace
import pytest
from rvw.formal.activation import guards
from rvw.formal.cores import run
from rvw.common.proc import run_group


def test_guard_extraction_does_not_guess_logical_antecedents():
    text = '''; yosys-smt2-assert 0 guarded source
(define-fun |top_a 0| ((state |top_s|)) Bool (or (|top#0| state) (not (|top#1| state))))
; yosys-smt2-assert 1 unsupported source
(define-fun |top_a 1| ((state |top_s|)) Bool true)'''
    result = guards(text, 'top')
    assert len(result) == 1
    assert result[0]['property_id'] == 'top:guarded'
    assert '(|top#1| state)' in result[0]['definition']


@pytest.mark.parametrize('blocked,status', [(False, 'reached'), (True, 'not_reached_bounded')])
def test_native_enable_activation(tmp_path, blocked, status):
    if not all(shutil.which(t) for t in ('yosys', 'z3')):
        pytest.skip('yosys and z3 required')
    root = tmp_path / 'run'
    (root / 'sby/model').mkdir(parents=True)
    rtl = tmp_path / 'top.v'
    rtl.write_text('module top(input enable,a); always @* begin ' +
                   ('assume(!enable);' if blocked else '') + ' if(enable) assert(a); end endmodule')
    il = root / 'sby/model/design.il'
    proc = run_group(['yosys', '-Q', '-T', '-p', f'read_verilog -formal {rtl}; prep -top top; write_rtlil {il}'], capture=True, timeout=10)
    assert proc.returncode == 0
    (root / 'result.json').write_text(json.dumps(dict(schema='rvw.formal/1', assertions=1, depth=3)))
    out = tmp_path / 'out'
    run(Namespace(result=str(root), depth=None, smt2=None, mapping=None, out=str(out), solver='z3', timeout=15, db=None, json=False))
    report = json.loads((out / 'result.json').read_text())
    assert report['property_activation'][0]['status'] == status
    assert report['bounded_model']['feasibility'] == 'sat'
    if blocked:
        assert report['property_activation'][0]['blocking_assumptions']


def test_metadata_does_not_mix_module_local_assertion_indices():
    from rvw.formal.activation import metadata
    model = '; yosys-smt2-module top\n; yosys-smt2-assert 0 wanted src\n; yosys-smt2-module child\n; yosys-smt2-assert 0 unrelated src\n'
    assert metadata(model, 'top', 'assert') == {'0': 'wanted'}


def test_native_aiger_job_needs_no_handwritten_smt(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yosys-abc', 'z3')):
        pytest.skip('native formal tools required')
    from rvw.cli import main
    rtl = tmp_path / 'counter.v'
    rtl.write_text('module top(input clk,reset,output reg [1:0] state=0); always @(posedge clk) if(reset) state<=0; else if(state==2) state<=0; else state<=state+1; always @* assert(state!=3); endmodule')
    root = tmp_path / 'aiger'
    assert main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top', '--clock', 'clk', '--reset', 'reset', '--depth', '4', '--engine', 'abc:bmc3', '--timeout', '20', '--out', str(root)]) == 0
    out = tmp_path / 'core'
    assert run(Namespace(result=str(root), depth=None, smt2=None, mapping=None, out=str(out), solver='z3', timeout=20, db=None, json=False)) == 0
    report = json.loads((out / 'result.json').read_text())
    assert report['bounded_model']['feasibility'] == 'sat'
    assert (out / 'bounded.smt2').is_file()
