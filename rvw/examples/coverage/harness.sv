module harness(input clk, input [3:0] a, input choose);
  wire [4:0] y;
  tiny dut(.clk(clk), .a(a), .choose(choose), .y(y));
  // A clock-sampled point. No restrictions on inputs or reset assumptions.
  always @(posedge clk) begin
    // RVW_POINT
  end
endmodule
