// Independent clocks can advance at different rates. Lockstep would falsely pass.
module top(input clk, other_clk);
  reg a = 0, b = 0;
  always @(posedge clk) a <= !a;
  always @(posedge other_clk) b <= !b;
  always @(posedge clk) assert(a == b);
endmodule
