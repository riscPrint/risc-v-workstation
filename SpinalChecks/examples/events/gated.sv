module top(input clk, en);
  reg q = 0;
  wire gated_clk = clk & en;
  always @(posedge gated_clk) q <= !q;
  always @(posedge clk) assert(q == 0);
endmodule
