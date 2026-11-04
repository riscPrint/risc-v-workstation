// Seeded property fault: the modulo-10 state can exceed 5.
module counter_fail(input clk, reset);
 reg [3:0] count;
 always @(posedge clk) begin
   if (reset) count <= 0;
   else count <= count == 9 ? 0 : count + 1;
   if (!reset) assert(count <= 5);
 end
endmodule
