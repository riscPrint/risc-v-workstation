"""Whole-parent native replay must not turn an absent X into a proof."""
import json
import shutil

import pytest

from rvw.cli import main

pytestmark = pytest.mark.skipif(not all(shutil.which(t) for t in
    ('yosys', 'sby', 'yices-smt2', 'iverilog', 'vvp')), reason='native tools required')


def invoke(tmp_path, extra=(), rtl=None):
    source = tmp_path / 'source.v'
    source.write_text(rtl or """module child(input clk, reset, enable, output y);
      reg u; assign y = enable ? u : 1'b0; endmodule
      module top(input clk, reset, input enable, output y);
      child u(clk,reset,enable,y); endmodule""")
    out = tmp_path / 'out'
    rc = main(['formal', 'x-context', '--verilog', str(source), '--top', 'top',
               '--signal', 'u.y', '--depth', '5', '--timeout', '20', '--out', str(out), *extra])
    return rc, json.loads((out / 'result.json').read_text())


@pytest.mark.parametrize('value,expected', [('1', 'reachable-in-core'), ('0', 'inconclusive')])
def test_parent_tie_controls_observation(tmp_path, value, expected):
    rc, result = invoke(tmp_path, ['--tie', 'enable=' + value])
    assert rc == 1
    assert result['inventory'][0]['disposition'] == expected
    assert bool(result['inventory'][0]['observations']) == (value == '1')


def test_missing_input_refused(tmp_path):
    with pytest.raises(SystemExit) as e:
        invoke(tmp_path)
    assert e.value.code == 2


def test_missing_hierarchy_never_confirms(tmp_path):
    _, result = invoke(tmp_path, ['--tie', 'enable=1', '--signal', 'missing.y'])
    assert all(t['disposition'] == 'inconclusive' for t in result['inventory'])


def test_reset_initializes_state(tmp_path):
    _, result = invoke(tmp_path, rtl="""module child(input clk, reset, output reg y);
      always @(posedge clk) if(reset) y<=0; endmodule
      module top(input clk,reset,output y); child u(clk,reset,y); endmodule""")
    assert result['inventory'][0]['disposition'] == 'inconclusive'
    assert not result['inventory'][0]['observations']


def test_timeout_never_confirms(tmp_path, monkeypatch):
    from rvw.formal import xcontext
    original = xcontext.common.run
    def stop(cmd, *args, **kwargs):
        if cmd[0] == 'vvp':
            (args[0] / 'context.log').write_text('RVW_CONTEXT 0 2 x\n')
            return 124, 0
        return original(cmd, *args, **kwargs)
    monkeypatch.setattr(xcontext.common, 'run', stop)
    _, result = invoke(tmp_path, ['--tie', 'enable=1'])
    assert result['inventory'][0]['disposition'] == 'inconclusive'
