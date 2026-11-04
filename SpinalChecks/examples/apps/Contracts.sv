module Contracts(input wire clk, reset, input wire [7:0] source,
 input wire write_enable, input wire [7:0] write_data, input wire pending,
 output wire [7:0] destination, output reg [7:0] state, output wire progress);
 assign destination = source;
 assign progress = pending;
 always @(posedge clk) if (reset) state <= 8'h12;
 else if (write_enable) state <= write_data;
endmodule
