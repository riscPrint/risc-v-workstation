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


@pytest.mark.skipif(shutil.which('yosys') is None, reason='needs Yosys')
def test_port_width_uses_selected_parameter(tmp_path):
    source = tmp_path / 'parameter.v'
    source.write_text('module m #(parameter WIDTH=4)(input [WIDTH-1:0] a, output [WIDTH-1:0] b); assign b=a; endmodule\n')
    ports = mapped.verilog_ports([source], 'm', params=['WIDTH=0x8'])
    assert all(p['width'] == 8 for p in ports)
