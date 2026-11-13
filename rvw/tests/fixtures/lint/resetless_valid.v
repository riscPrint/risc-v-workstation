module ResetlessValid(input clk, reset, enable, output reg valid, reset_seen);
  always @(posedge clk) valid <= enable;
  always @(posedge clk or posedge reset)
    if (reset) reset_seen <= 1'b0; else reset_seen <= enable;
endmodule
