`timescale 1ns/1ps
module tb;
  reg clk = 0, reset = 1;
  reg [3:0] q = 0;
  always #5 clk = ~clk;
  always @(posedge clk) begin
    if (reset) q <= 0;
    else q <= q + 1;
  end
  initial begin
    @(posedge clk); #1;
    if (q !== 0) $fatal(1, "reset");
    reset = 0;
    for (int i = 1; i <= 4; i++) begin
      @(posedge clk); #1;
      if (q !== i[3:0]) $fatal(1, "NBA/delay order");
      $display("OBS %0d %0d", $time, q);
    end
    $display("RVW_PASS");
    $finish;
  end
endmodule
