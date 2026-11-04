`timescale 1ns/1ps
module tb;
  reg clk = 0, reset = 1;
  wire [3:0] q;
  counter dut(clk, reset, q);
  always #5 clk = ~clk;
  initial begin
    @(posedge clk); #1;
    if (q !== 0) $fatal(1, "reset");
    reset = 0;
    repeat (3) @(posedge clk);
    #1;
    if (q !== 3) $fatal(1, "count");
    $display("RVW_PASS");
    $finish;
  end
endmodule
