"""Round 16: single-clock exclusions must refuse asynchronous state controls."""
import copy
import json
import shutil

import pytest

from rvw.common.proc import run_group
from rvw.cov import proof
from .test_proof import _setup, needs_sby, needs_yosys


DUT = """module dut(input clk, input rst, output reg q=0, output reg r=0);
always @(posedge clk or posedge rst) if(rst) q<=0; else q<=!q;
always @(posedge clk) if(rst) r<=0; else r<=!r;
endmodule
"""
HARNESS = """module h(input clk, input rst);
wire q,r; dut d(clk,rst,q,r);
always @(posedge clk) begin
// RVW_POINT
end
endmodule
"""


@needs_sby
@pytest.mark.parametrize("extra", [{}, {"reset": None}, {"reset": "rst", "reset_active_low": False}])
def test_async_reset_pulse_excludes_nothing(tmp_path, extra):
    cfg, db = _setup(tmp_path, HARNESS, "!rst && q != r", dut=DUT, extra=extra)
    result = proof.prove(cfg, db, tmp_path / "proof", timeout=30)
    assert not result['sanity']['passed']
    assert 'asynchronous' in result['sanity']['error']
    point = result['points'][0]
    assert not point['unreachable'] and point['jobs'] == {}
    assert not list((tmp_path / 'proof').glob('*.sby'))
    applied = proof.apply_exclusions(json.loads(db.read_text()), tmp_path / 'proof/exclusions.json')
    assert 'exclusion' not in applied['points'][0]


@needs_sby
def test_apply_rechecks_async_state_in_saved_netlist(tmp_path, monkeypatch):
    cfg, db = _setup(tmp_path, HARNESS, "!rst && q != r", dut=DUT)
    # Recreate the unsafe old evidence with only the new guard disabled. All solver jobs are real.
    with monkeypatch.context() as patch:
        patch.setattr(proof, 'async_state_problems', lambda modules: [], raising=False)
        result = proof.prove(cfg, db, tmp_path / 'proof', timeout=30)
    assert result['points'][0]['unreachable']
    path = tmp_path / 'exclusions.json'
    data = json.loads(db.read_text())
    result['schema'] = 'rvw.coverage-exclusions/5'
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match='schema.*rerun'):
        proof.apply_exclusions(data, path)
    # Relabeling the old file cannot bypass the check. Do not trust its stored guard verdict.
    result['schema'] = proof.EXCLUSIONS_SCHEMA
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match='asynchronous'):
        proof.apply_exclusions(data, path)


@needs_yosys
@pytest.mark.parametrize('placement', ['design', 'harness', 'unused', 'tied'])
def test_async_controls_are_checked_before_optimization(tmp_path, placement):
    dut, harness = DUT, HARNESS
    if placement == 'harness':
        dut = DUT.replace(' or posedge rst', '')
        harness = HARNESS.replace('wire q,r;', 'reg a=0; always @(posedge clk or posedge rst) '
                                  'if(rst) a<=0; else a<=!a;\nwire q,r;')
    elif placement == 'unused':
        dut = DUT.replace(' or posedge rst', '') + DUT.replace('module dut(', 'module async_dut(')
        harness = HARNESS.replace('wire q,r;', 'wire unused_q,unused_r; '
                                  'async_dut unused(clk,rst,unused_q,unused_r);\nwire q,r;')
    elif placement == 'tied':
        harness = HARNESS.replace('dut d(clk,rst,q,r)', "dut d(clk,1'b0,q,r)")
    cfg, _ = _setup(tmp_path, harness, '!rst && q != r', dut=dut, extra={'reset': None})
    config = json.loads(cfg.read_text())
    netlist = proof.elaborate(tmp_path / 'proof', [tmp_path / 'dut.v'], harness, 'h', yosys=shutil.which('yosys'))
    # Even a forged clean clock record must not disable the independent state-control check.
    netlist['clock']['problems'] = []
    plan = proof.sanity_plan(config, netlist)
    assert plan['expression'] is None and 'asynchronous' in plan['error']


@pytest.mark.parametrize('kind', ['$adff', '$adffe', '$aldff', '$aldffe', '$dffsr', '$dffsre',
                                 '$sr', '$dlatch', '$adlatch', '$dlatchsr', '$_DFF_PP0_',
                                 '$_DLATCH_P_', '$future_ff'])
def test_async_state_cell_types_refuse(kind):
    modules = {'m': {'cells': {'q': {'type': kind, 'connections': {}}}}}
    assert proof.async_state_problems(modules)


@pytest.mark.parametrize('kind,port', [('$memrd_v2', 'ARST'), ('$mem_v2', 'RD_ARST')])
def test_memory_async_reset_refuses_unless_inactive(kind, port):
    modules = {'m': {'cells': {'mem': {'type': kind, 'connections': {port: ['0', '0']}}}}}
    assert proof.async_state_problems(modules) == []
    for bit in [2, '1', 'x', 'z']:
        changed = copy.deepcopy(modules)
        changed['m']['cells']['mem']['connections'][port][1] = bit
        assert proof.async_state_problems(changed)


@pytest.mark.skipif(not all(shutil.which(t) for t in ('iverilog', 'vvp')), reason='needs Icarus')
def test_async_reset_pulse_is_reachable_in_simulation(tmp_path):
    (tmp_path / 'dut.v').write_text(DUT)
    (tmp_path / 'tb.v').write_text('''module tb;
reg clk=0, rst=0;
wire q,r; dut d(clk,rst,q,r);
always #5 clk=~clk;
always @(posedge clk) if (!rst && q!=r) begin
  $display("REACHABLE t=%0t", $time); $finish;
end
initial begin #7 rst=1; #1 rst=0; #30 $fatal(1,"point never reached"); end
endmodule
''')
    compiled = run_group(['iverilog', '-g2012', '-s', 'tb', '-o', 'sim', 'dut.v', 'tb.v'],
                         cwd=tmp_path, capture=True, timeout=10)
    assert compiled.returncode == 0, compiled.stderr
    result = run_group(['vvp', 'sim'], cwd=tmp_path, capture=True, timeout=10)
    assert result.returncode == 0 and 'REACHABLE t=15' in result.stdout
