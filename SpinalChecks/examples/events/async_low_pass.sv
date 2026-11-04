// Both registers react to every sampled reset assertion, including between edges.
module top(input clk, rst);
  reg q = 0, r = 0;
  always @(posedge clk or negedge rst) if (!rst) q <= 0; else q <= !q;
  always @(posedge clk or negedge rst) if (!rst) r <= 0; else r <= !r;
  always @(posedge clk) if (rst) assert(q == r);
  // Reset can pulse only while clk is low. It cannot clear the sync register.
  always @* assume(rst || !clk);
endmodule
