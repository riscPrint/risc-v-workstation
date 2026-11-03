"""Independent native X cases and conservative per-target dispositions."""
import json
import shutil
import pytest
from rvw.cli import main

pytestmark = pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','sby','yices-smt2','iverilog','vvp')),
                                reason='native formal and four-state tools required')


def run(tmp_path, rtl, extra=()):
    source = tmp_path / 'dut.v'
    source.write_text(rtl)
    out = tmp_path / 'out'
    rc = main(['formal', 'xprop', '--verilog', str(source), '--top', 'top', '--outputs',
               '--replay', 'icarus', '--depth', '7', '--out', str(out), *extra])
    return rc, json.loads((out / 'result.json').read_text())


@pytest.mark.parametrize('expr,expected', [("a & 1'bx", 'confirmed'), ('a & 1\'b0','not_reported'),
                                         ("1'bz", 'confirmed')])
def test_clock_free_known_cases(tmp_path, expr, expected):
    rc, result = run(tmp_path, f'module top(input a, output y); assign y={expr}; endmodule', ['--combinational'])
    assert result['inventory'][0]['disposition'] == expected
    assert rc == (0 if expected == 'not_reported' else 1)


def test_memory_and_reset_release(tmp_path):
    _, result = run(tmp_path, '''module top(input clk, reset, input [1:0] addr, output reg [7:0] y);
      reg [7:0] mem[0:3];
      always @(posedge clk) if(reset) y<=0; else y<=mem[addr]; endmodule''')
    assert result['inventory'][0]['disposition'] == 'confirmed'
    assert result['replay']['backend'] == 'icarus'


def test_power_transition(tmp_path):
    _, result = run(tmp_path, '''module top(input clk, reset, power, output reg y);
      reg uninit;
      always @(posedge clk) if(reset) y<=0; else if(power) y<=uninit; else y<=0; endmodule''')
    assert result['inventory'][0]['disposition'] == 'confirmed'


def test_clock_free_refuses_sequential(tmp_path):
    source = tmp_path / 'seq.v'
    source.write_text('module top(input a,output reg y); always @(posedge a) y<=a; endmodule')
    with pytest.raises(SystemExit) as exc:
        main(['formal','xprop','--verilog',str(source),'--top','top','--outputs',
              '--combinational','--out',str(tmp_path/'out')])
    assert exc.value.code == 2


def test_sweep_inventory(tmp_path):
    source = tmp_path/'dut.v'
    source.write_text("module child(input a, output y); assign y=a & 1'bx; endmodule\n"
                      'module top(input a, output y); child u(a,y); endmodule')
    out = tmp_path/'sweep'
    assert main(['formal','x-sweep','--verilog',str(source),'--top','top','--out',str(out),
                 '--module-timeout','20','--campaign-timeout','60']) == 1
    result = json.loads((out/'result.json').read_text())
    assert {m['module'] for m in result['modules']} == {'top','child'}
    assert all(m['disposition']=='confirmed' for m in result['modules'])


def test_undefined_input_preserved(tmp_path):
    _, result = run(tmp_path, 'module top(input a, output y); assign y=a; endmodule',
                    ['--combinational', '--x-inputs'])
    assert result['inventory'][0]['disposition'] == 'confirmed'


def test_incomplete_assignment_refused(tmp_path):
    source = tmp_path/'latch.v'
    source.write_text('module top(input a,en,output reg y); always @* if(en) y=a; endmodule')
    with pytest.raises(SystemExit) as exc:
        main(['formal','xprop','--verilog',str(source),'--top','top','--outputs',
              '--combinational','--out',str(tmp_path/'out')])
    assert exc.value.code == 2


def test_missing_trace_never_confirms(tmp_path):
    from types import SimpleNamespace
    from rvw.formal.xreplay import replay
    # No candidate means that replay has no confirmation evidence.
    result = {'x_reaches': [], 'inventory': [{'assert':'rvw_x_0', 'disposition':'not_reported'}]}
    replay(SimpleNamespace(), tmp_path, [], [], result, None, {}, 0, 0, True)
    assert result['replay']['status'] == 'inconclusive'


def test_optimistic_source_if_does_not_confirm_encoded_mux(tmp_path):
    _, result = run(tmp_path, """module top(input clk,a,output reg y);
      reg unknown_select;
      always @* if(unknown_select && a) y=1; else y=0; endmodule""")
    assert result['x_reaches']
    assert result['inventory'][0]['disposition'] == 'inconclusive'
    assert result['replay']['traces'][0]['status'] == 'complete'


def test_sweep_refuses_failed_child_receipt(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    from rvw.formal import xsweep
    source = tmp_path/'dut.v'
    source.write_text('module top(input a, output y); assign y=a; endmodule')
    def failed(cmd, **kwargs):
        directory = Path(cmd[cmd.index('--out')+1])
        directory.mkdir(parents=True, exist_ok=True)
        (directory/'result.json').write_text('{"status":"pass"}')
        return SimpleNamespace(timed_out=False, returncode=2)
    monkeypatch.setattr(xsweep, 'run_group', failed)
    out = tmp_path/'sweep'
    main(['formal','x-sweep','--verilog',str(source),'--top','top','--out',str(out)])
    result = json.loads((out/'result.json').read_text())
    assert result['modules'][0]['disposition'] == 'inconclusive'


def test_vectors_preserve_masks_and_refuse_undefined_defined_bits(tmp_path):
    from types import SimpleNamespace
    from rvw.formal.xreplay import vectors
    trace = tmp_path/'trace.vcd'
    header = '''$timescale 1ns $end
$var integer 32 t smt_step $end
$var event 1 ! smt_clock $end
$scope module rvw_xprop_top $end
$var wire 2 a data $end
$var wire 2 m mask $end
$upscope $end
$enddefinitions $end
#0
1!
b0 t
b01 a
b10 m
#10
1!
b1 t
'''
    trace.write_text(header)
    ports = [SimpleNamespace(name='data', width=2)]
    assert vectors(trace, ports, {'data':'mask'}) == [{'data':'x1'}]
    trace.write_text(header.replace('b01 a', 'b0z a'))
    with pytest.raises(ValueError, match='missing defined'):
        vectors(trace, ports, {'data':'mask'})
    with pytest.raises(ValueError, match='undefined counterexample'):
        vectors(trace, ports)


def test_unencoded_blackbox_cannot_earn_clean_result(tmp_path):
    _, result = run(tmp_path, '''(* blackbox *) module bb(output y); endmodule
      module top(input clk, output y); bb u(y); endmodule''')
    assert result['status'] != 'pass'
    assert 'bb' in result['unencoded_cells']


def test_first_failure_preserves_unreported_targets(tmp_path):
    _, result = run(tmp_path, """module top(input clk, reset, output y, output z);
      reg u; assign y=u; assign z=0; endmodule""", ['--first-failure'])
    assert result['inventory'][0]['disposition'] == 'confirmed'
    assert result['inventory'][1]['disposition'] == 'not_reported'
    script = (tmp_path / 'out' / 'xprop.sby').read_text()
    assert '--keep-going' not in script
