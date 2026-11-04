`timescale 1ns/1ps
module tb;
  reg clk = 0, reset = 0;
  reg [3:0] q;
  wire z = 1'bz;
  always #5 clk = ~clk;
  always @(posedge clk) begin
    if (reset) q <= 0;
    else q <= q + 1;
  end
  initial begin
    #1;
    if (q !== 4'bxxxx || z !== 1'bz || (q & 4'b0000) !== 0)
      $fatal(1, "X/Z semantics");
    @(posedge clk); #1;
    if (q !== 4'bxxxx) $fatal(1, "unknown arithmetic");
    reset = 1;
    @(posedge clk); #1;
    if (q !== 0) $fatal(1, "reset did not clear X");
    reset = 0;
    @(posedge clk); #1;
    if (q !== 1) $fatal(1, "post-reset count");
    $display("RVW_PASS");
    $finish;
  end
endmodule
