module clock_probe(input clk, output wire [63:0] hdl_time); assign hdl_time = $time; endmodule
