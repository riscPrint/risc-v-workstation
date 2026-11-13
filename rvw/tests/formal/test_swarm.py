from argparse import Namespace
import json
from pathlib import Path

import pytest
from rvw.formal import cli, swarm


def test_selection():
    assert swarm.select_cycles(2, 12, 4) == [2, 5, 8, 12]
    assert swarm.select_cycles(3, 3, 1) == [3]
    for values in [(0, 2, 1), (3, 2, 1), (1, 2, 3), (1, 2, 0)]:
        with pytest.raises(ValueError):
            swarm.select_cycles(*values)


def test_swarm_freezes_inputs_keeps_failures_and_never_proves(tmp_path, monkeypatch):
    source = tmp_path / 'top.sv'
    source.write_text('module top(input clk); endmodule')
    trace = tmp_path / 'trace.vcd'
    trace.write_text('original trace')
    statuses = iter(['pass', 'fail', 'unknown'])
    def flow(name, args):
        assert name == 'from_sim'
        assert Path(args.trace).read_text() == 'original trace'
        assert 'module top' in Path(args.verilog[0]).read_text()
        assert args.timeout <= 3
        source.write_text('changed')
        trace.write_text('changed')
        out = Path(args.out)
        out.mkdir()
        (out / 'result.json').write_text(json.dumps({'status': next(statuses),
                                                    'restrictions': ['conditional']}))
    monkeypatch.setattr(cli, '_flow', flow)
    args = Namespace(out=tmp_path / 'out', start_cycle=1, end_cycle=9, samples=3,
                     top='top', depth=4, budget=30, timeout=3, json=False, verilog=[str(source)],
                     trace=str(trace), checks=None, engine='smtbmc:yices')
    assert swarm.run(args) == 1
    result = json.loads((args.out / 'result.json').read_text())
    assert result['status'] == 'inconclusive'
    assert result['bounded_passes'] == result['conditional_failures'] == 1
    assert result['missing_cycles'] == []
    assert [a['cycle'] for a in result['attempts']] == [1, 5, 9]
    assert all(a['restrictions'] == ['conditional'] for a in result['attempts'])


def test_swarm_records_invalid_states(tmp_path, monkeypatch):
    source = tmp_path / 'top.sv'
    source.write_text('module top; endmodule')
    trace = tmp_path / 'trace.vcd'
    trace.write_text('trace')
    monkeypatch.setattr(cli, '_flow', lambda *a: (_ for _ in ()).throw(SystemExit(2)))
    args = Namespace(out=tmp_path / 'out', start_cycle=1, end_cycle=1, samples=1,
                     top='top', depth=4, budget=30, timeout=None, json=False, verilog=[str(source)],
                     trace=str(trace), checks=None, engine='smtbmc:yices')
    swarm.run(args)
    result = json.loads((args.out / 'result.json').read_text())
    assert result['attempts'][0]['status'] == 'error'
    assert result['bounded_passes'] == 0


def test_native_swarm(tmp_path):
    import shutil
    import sys
    from rvw.common.proc import run_group
    if not all(shutil.which(t) for t in ('sby', 'yosys', 'yices-smt2', 'vcd2fst')):
        pytest.skip('optional native formal tools missing')
    source = tmp_path / 'top.sv'
    source.write_text("module top(input clk); reg [3:0] count=0; "
                      "always @(posedge clk) begin count<=count+1; assert(count<16); end endmodule")
    trace = tmp_path / 'trace.vcd'
    trace.write_text("""$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var reg 4 " count [3:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b0000 "
#5
1!
b0001 "
#10
0!
#15
1!
b0010 "
#20
0!
#25
1!
b0011 "
""")
    out = tmp_path / 'native'
    proc = run_group([sys.executable, '-m', 'rvw', 'formal', 'swarm', '--verilog', str(source),
                      '--top', 'top', '--trace', str(trace), '--end-cycle', '3', '--samples', '2',
                      '--budget', '40', '--timeout', '15', '--depth', '4', '--out', str(out)],
                     capture=True, timeout=60)
    assert proc.returncode == 1, (proc.stdout, proc.stderr)
    result = json.loads((out / 'result.json').read_text())
    assert result['bounded_passes'] == 2, (result, proc.stderr)
    assert result['status'] == 'inconclusive'
    for attempt in result['attempts']:
        detail = json.loads((out / attempt['result']).read_text())
        assert detail['proof_kind'] == 'bounded'
        assert detail['reachability']['status'] == 'reachable'
        assert attempt['state_coverage']['ff_bits_from_trace'] >= 4


def test_swarm_budget_keeps_unstarted_cycles(tmp_path, monkeypatch):
    source = tmp_path / 'top.sv'
    source.write_text('module top; endmodule')
    trace = tmp_path / 'trace.vcd'
    trace.write_text('trace')
    ticks = iter([0, 31])
    monkeypatch.setattr(swarm.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(cli, '_flow', lambda *a: pytest.fail('expired budget'))
    args = Namespace(out=tmp_path / 'out', start_cycle=1, end_cycle=3, samples=2,
                     top='top', depth=4, budget=30, timeout=None, json=False,
                     verilog=[str(source)], trace=str(trace), checks=None, engine='smtbmc:yices')
    swarm.run(args)
    result = json.loads((args.out / 'result.json').read_text())
    assert result['stop_reason'] == 'budget_exhausted'
    assert result['missing_cycles'] == [1, 3]
    assert result['attempts'] == []


def test_coverage_selection_rotates_engines(tmp_path, monkeypatch):
    import hashlib
    source = tmp_path / 'top.sv'
    source.write_text('module top; endmodule')
    trace = tmp_path / 'trace.vcd'
    trace.write_text('trace')
    state_plan = tmp_path / 'states.json'
    state_plan.write_text(json.dumps({'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
        'holes': ['wrap', 'full'], 'states': [{'cycle': 1, 'targets': []},
        {'cycle': 5, 'targets': ['wrap']}, {'cycle': 9, 'targets': ['full']}]}))
    engines = []
    def flow(name, child):
        engines.append(child.engine)
        out = Path(child.out)
        out.mkdir()
        (out / 'result.json').write_text('{"status":"pass"}')
    monkeypatch.setattr(cli, '_flow', flow)
    args = Namespace(out=tmp_path / 'out', start_cycle=1, end_cycle=9, samples=2,
                     top='top', depth=4, budget=30, timeout=3, json=False,
                     verilog=[str(source)], trace=str(trace), checks=None, engine='smtbmc:yices',
                     engine_pool=['smtbmc:yices', 'abc:bmc3'], state_plan=state_plan)
    assert swarm.run(args) == 1
    r = json.loads((args.out / 'result.json').read_text())
    assert r['selection']['cycles'] == [5, 9]
    assert engines == ['smtbmc:yices', 'abc:bmc3']
    assert r['status'] == 'inconclusive'
