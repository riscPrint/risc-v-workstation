module top(input clk, rst, d, output reg q);
  always @(posedge clk or posedge rst) if(rst) q <= d; else q <= !q;
  always @(posedge clk) assert(q == 0);
endmodule
