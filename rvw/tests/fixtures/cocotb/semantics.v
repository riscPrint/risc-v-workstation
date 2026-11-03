`timescale 1ns/1ps
module semantics(input clk, input reset, input enable, output reg [7:0] count,
                 output wire unknown_value, output wire high_z);
  assign unknown_value = 1'bx;
  assign high_z = 1'bz;
  always @(posedge clk) begin
    if(reset) count <= 0;
    else if(enable) count <= count + 1;
  end
endmodule
