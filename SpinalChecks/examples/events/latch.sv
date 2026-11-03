module top(input clk, en, d, output reg q);
  always @* if(en) q <= d;
  always @(posedge clk) assert(q == 0);
endmodule
