"""Round 15: waveform grammar, resumed assumptions, and bounded reachability."""
import json
import shutil

import pytest

from rvw.cli import main
from rvw.formal import common, vcdsnap

HEADER = '''$timescale 1 ps $end
$scope module tb $end $scope module dut $end
$var wire 1 ! clk $end
$var reg 1 " q $end
$upscope $end $upscope $end
$enddefinitions $end
'''


needs_tools = pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys', 'sby', 'vcd2fst')),
                                reason='needs oss-cad-suite')


@needs_tools
@pytest.mark.parametrize('engine', ['smtbmc:yices', 'abc:bmc3'])
@pytest.mark.parametrize('missing', [False, True])
@pytest.mark.parametrize('assumption', ['initial assume(!q);', 'always @* if ($initstate) assume(!q);'])
def test_replay_drops_design_time_zero_assumptions(tmp_path, engine, missing, assumption):
    rtl = tmp_path / 'top.sv'
    rtl.write_text('''module top(input clk, input set, output reg q);
initial q=0;
always @(posedge clk) if(set) q<=1;
initial assume(!q);
always @(posedge clk) assert(!q);
endmodule
'''.replace('initial assume(!q);', assumption))
    trace = tmp_path / 'trace.vcd'
    header = HEADER.replace('$var reg 1 " q $end', '') if missing else HEADER
    trace.write_text(header.replace('$upscope $end $upscope $end',
                                      '$var wire 1 # set $end $upscope $end $upscope $end')
                     + ('#0 0! 1# #5 1! 0# #10 0!' if missing else '#0 0! 1# 0" #5 1! 0# 1" #10 0!').replace(' ', '\n') + '\n')
    out = tmp_path / 'run'
    rc = main(['formal', 'from-sim', '--verilog', str(rtl), '--top', 'top', '--trace', str(trace),
               '--scope', 'tb.dut', '--cycle', '1', '--depth', '3', '--tie', 'set=0',
               '--engine', engine, '--out', str(out), '--json'])
    r = json.loads((out / 'result.json').read_text())
    assert rc == 1 and r['status'] == 'fail'
    assert r['state']['ff_bits_free'] == int(missing)
    assert r['removed_initial_assumptions']


@needs_tools
@pytest.mark.parametrize('engine', ['smtbmc:yices', 'abc:bmc3'])
@pytest.mark.parametrize('flow', ['bmc', 'from-sim', 'xprop'])
def test_unsatisfiable_runtime_assumptions_cannot_pass(tmp_path, flow, engine):
    rtl = tmp_path / 'top.sv'
    rtl.write_text('''module top(input clk, input a, output reg y);
always @(posedge clk) begin if(a) y<=0; assume(a); assume(!a); assert(!y); end
endmodule
''')
    out = tmp_path / 'run'
    extra = ['--outputs'] if flow == 'xprop' else []
    if flow == 'from-sim':
        trace = tmp_path / 'trace.vcd'
        trace.write_text(HEADER.replace('$enddefinitions', '$var wire 1 # a $end $enddefinitions')
                         .replace('$upscope $end $upscope $end', '')
                         .replace('$enddefinitions', '$upscope $end $upscope $end $enddefinitions')
                         + '#0\n0!\n0"\n0#\n#5\n1!\n#10\n0!\n')
        extra = ['--trace', str(trace), '--scope', 'tb.dut', '--cycle', '1']
    rc = main(['formal', flow, '--verilog', str(rtl), '--top', 'top', '--depth', '5',
               '--engine', engine, '--out', str(out), '--json', *extra])
    r = json.loads((out / 'result.json').read_text())
    if flow == 'xprop' and engine == 'abc:bmc3':
        # ABC refuses the X constants left in this model. It still must never pass.
        assert rc == 1 and r['status'] == 'error'
    else:
        assert rc == 1 and r['status'] == 'unknown'
        assert r['reachability']['status'] == 'unreachable'


@needs_tools
def test_assumptions_must_have_a_path_through_the_last_step(tmp_path):
    rtl = tmp_path / 'top.sv'
    rtl.write_text('''module top(input clk, output reg [3:0] q);
initial q=0;
always @(posedge clk) begin q<=q+1; assume(q<2); assert(q<4); end
endmodule
''')
    out = tmp_path / 'run'
    rc = main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top', '--depth', '6',
               '--out', str(out), '--json'])
    r = json.loads((out / 'result.json').read_text())
    assert rc == 1 and r['status'] == 'unknown'
    assert r['reachability']['status'] == 'unreachable'


def test_ambiguous_default_scope_is_refused(tmp_path, monkeypatch):
    rtl = tmp_path / 'top.sv'
    rtl.write_text('module top(input clk); endmodule')
    trace = tmp_path / 'trace.vcd'
    trace.write_text('')
    monkeypatch.setattr(common, 'need', lambda *a: None)
    monkeypatch.setattr(common, 'probe_clocks', lambda *a: None)
    monkeypatch.setattr(vcdsnap, 'scopes', lambda *a, **kw: ['tb.top', 'tb.other.top'])
    with pytest.raises(SystemExit):
        main(['formal', 'from-sim', '--verilog', str(rtl), '--top', 'top',
              '--trace', str(trace), '--cycle', '1', '--out', str(tmp_path / 'run')])


@needs_tools
@pytest.mark.parametrize('engine', ['smtbmc:yices', 'abc:bmc3'])
def test_pass_has_a_path_through_the_last_step(tmp_path, engine):
    rtl = tmp_path / 'top.sv'
    rtl.write_text("""module top(input clk, output reg [3:0] q);
initial q=0;
always @(posedge clk) begin q<=q+1; assert(q<8); end
endmodule
""")
    out = tmp_path / 'run'
    assert main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top', '--depth', '4',
                 '--engine', engine, '--out', str(out), '--json']) == 0
    r = json.loads((out / 'result.json').read_text())
    assert r['status'] == 'pass' and r['reachability']['status'] == 'reachable'


@pytest.mark.parametrize('rc', [0, 2, 124])
def test_reachability_requires_solver_log_evidence(tmp_path, monkeypatch, rc):
    from types import SimpleNamespace
    from rvw.formal import flows

    monkeypatch.setattr(common, 'run', lambda *a, **kw: (rc, 0.0))
    args = SimpleNamespace(depth=4, timeout=5)
    result = flows._reachability(tmp_path, 'top', args, 5)
    assert result['status'] == 'unknown'
    assert result['solver'] == {'exit': rc, 'log_rc': None}
