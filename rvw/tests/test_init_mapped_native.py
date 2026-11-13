"""`rvw init` mapped mode with native Yosys."""
import shutil

import pytest

from rvw.init import mapped


@pytest.mark.skipif(shutil.which('yosys') is None, reason='needs Yosys')
def test_real_yosys_ports(tmp_path):
    source = tmp_path / 'm.v'
    source.write_text('module m(input clk, input [3:0] a, output reg [7:0] b); always @(posedge clk) b <= a; endmodule\n')
    assert mapped.verilog_ports([source], 'm') == [dict(name='clk', dir='in', width=1),
                                                    dict(name='a', dir='in', width=4),
                                                    dict(name='b', dir='out', width=8)]
