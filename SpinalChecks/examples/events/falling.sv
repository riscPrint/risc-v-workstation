module top(input clk);
  reg q = 0;
  always @(negedge clk) q <= !q;
  always @(posedge clk) assert(q == 0);
endmodule
