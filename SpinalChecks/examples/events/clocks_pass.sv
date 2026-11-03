// Each domain has its own invariant, for every relative rate and phase.
module top(input clk, other_clk);
  reg [1:0] a = 0, b = 0;
  always @(posedge clk) a <= a == 2 ? 0 : a + 1;
  always @(posedge other_clk) b <= b == 2 ? 0 : b + 1;
  always @(posedge clk) assert(a < 3);
  always @(posedge other_clk) assert(b < 3);
endmodule
