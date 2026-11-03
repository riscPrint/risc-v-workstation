"""Small native reference cases. No core build."""
import json
import shutil
import sys

import pytest

from rvw.common.proc import run_group


@pytest.mark.parametrize('mode,engine,tool', [
    ('bmc', 'btor:pono', 'pono'), ('bmc', 'btor:btormc', 'btormc'),
    ('prove', 'aiger:avy', 'avy'), ('prove', 'abc:pdr', 'yosys-abc')])
@pytest.mark.parametrize('bad', [False, True])
def test_engine_reference(tmp_path, mode, engine, tool, bad):
    if not all(shutil.which(t) for t in (tool, 'sby', 'yosys', 'yices-smt2')):
        pytest.skip('optional native engine missing')
    source = tmp_path / 'counter.sv'
    source.write_text('module counter(input clk); reg [3:0] count=0;\n'
                      'always @(posedge clk) begin count <= count+1;\n'
                      f'assert(count < {8 if bad else 16}); end endmodule\n')
    out = tmp_path / 'out'
    run = run_group([sys.executable, '-m', 'rvw', 'formal', mode, '--verilog', str(source),
                     '--top', 'counter', '--engine', engine, '--depth', '12',
                     '--out', str(out), '--timeout', '20'], capture=True, timeout=40)
    result = json.loads((out / 'result.json').read_text())
    if engine == "aiger:avy" and not bad and result["status"] == "error":
        # Native Avy can crash on a constant safe AIG. It must never earn a pass.
        assert run.returncode == 1
        log = (out / "sby" / "logfile.txt").read_text()
        assert "returncode=-11" in log
        return
    assert run.returncode == int(bad), (run.stdout, run.stderr)
    assert result['status'] == ('fail' if bad else 'pass')
    assert result['proof_kind'] == ('unbounded' if mode == 'prove' else 'bounded')


def test_cut_failure_is_not_a_concrete_bug(tmp_path):
    if not all(shutil.which(t) for t in ('sby', 'yosys', 'yices-smt2')):
        pytest.skip('optional native tools missing')
    source = tmp_path / 'held.sv'
    source.write_text('module held(input clk); reg [2:0] count=0;\n'
                      'always @(posedge clk) begin count <= count == 5 ? 0 : count+1; assert(count <= 5); end endmodule\n')
    out = tmp_path / 'out'
    run = run_group([sys.executable, '-m', 'rvw', 'formal', 'bmc', '--verilog', str(source),
                     '--top', 'held', '--cut', 'count:3', '--depth', '4',
                     '--out', str(out), '--timeout', '20'], capture=True, timeout=40)
    assert run.returncode == 1, (run.stdout, run.stderr)
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'unknown'
    assert result['abstraction_counterexample'] is True
