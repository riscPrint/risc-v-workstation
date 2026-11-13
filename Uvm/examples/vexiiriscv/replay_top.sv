`timescale 1ns/1ps
module replay_top;
 bit clk=0; always #5 clk=~clk;
endmodule
