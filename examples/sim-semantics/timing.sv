`timescale 1ns/1ps
module tb;
  reg clk = 0;
  integer value = 0;
  integer branch_a = 0, branch_b = 0;
  always #5 clk = ~clk;
  always @(posedge clk) value <= value + 1;
  initial begin
    fork
      begin #2; branch_a = 1; end
      begin #3; branch_b = 1; end
    join
    if ($time != 3 || !branch_a || !branch_b) $fatal(1, "fork/join delays");
    @(posedge clk); #1;
    if ($time != 6 || value != 1) $fatal(1, "NBA event scheduling");
    repeat (2) @(posedge clk);
    #1;
    if ($time != 26 || value != 3) $fatal(1, "repeat event scheduling");
    $display("RVW_PASS");
    $finish;
  end
endmodule
