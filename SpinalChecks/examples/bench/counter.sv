// Handwritten HWMCC-style finite-state safety fixture, not an HWMCC submission.
module counter(input clk, reset);
 reg [3:0] count;
 always @(posedge clk) begin
   if (reset) count <= 0;
   else count <= count == 9 ? 0 : count + 1;
   if (!reset) assert(count <= 9);
 end
endmodule
