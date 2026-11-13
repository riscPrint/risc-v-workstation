import shutil
from pathlib import Path
import pytest
from rvw.common.capture import Capture
from rvw.formal.internal_exposure import expose


def test_exact_internal_signal_and_width(tmp_path):
    if not shutil.which('yosys'):
        pytest.skip('Yosys required')
    source = tmp_path/'top.sv'
    source.write_text('module top(input clk,reset, output y); reg [1:0] state; always @(posedge clk) if(reset) state<=0; else state<=state+1; assign y=state[0]; endmodule')
    plan = {'top':'top','internal_ports':{'state':2}}
    files = expose(plan,[source],tmp_path/'export',Capture(tmp_path/'capture'),10)
    assert 'output [1:0] state' in files[0].read_text()
    with pytest.raises(ValueError, match='width'):
        expose(dict(plan,internal_ports={'state':3}),[source],tmp_path/'wrong',Capture(tmp_path/'capture2'),10)
