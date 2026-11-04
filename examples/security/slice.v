// Small RV32 instruction slice. Not a general-purpose RISC-V core.
// PC 0: beq x0,x0,+8. PC 8: add x3,x1,x2. Registers enter after reset.
// The skipped load at PC 4 is represented only by a transient cache update.
module slice #(parameter CACHE_LEAK=0, TIMING_LEAK=0, TRACE_LEAK=0, TEST_LEAK=0)
(input clk, reset, input [31:0] secret, public_data,
 output reg [31:0] pc, result, output reg retire, output reg [31:0] insn,
 output reg [4:0] rd, output reg [3:0] cache, output [31:0] protected_trace,
 output [31:0] test_output);
 reg waiting;
 assign protected_trace = TRACE_LEAK ? secret : 0;
 assign test_output = TEST_LEAK ? secret : 0;
 always @(posedge clk) begin
   if (reset) begin
     pc <= 32'h80000000; result <= 0; retire <= 0;
     insn <= 0; rd <= 0; cache <= 0; waiting <= 0;
   end else begin
     retire <= 0;
     if (pc == 32'h80000000) begin
       insn <= 32'h00000463; rd <= 0; result <= 0;
       retire <= 1; pc <= 32'h80000008;
       if (CACHE_LEAK) cache <= 4'b0001 << secret[1:0];
     end else if (pc == 32'h80000008) begin
       if (TIMING_LEAK && secret[0] && !waiting) waiting <= 1;
       else begin
         insn <= 32'h002081b3; rd <= 3; result <= secret + public_data;
         retire <= 1; pc <= 32'h8000000c;
       end
     end
   end
 end
endmodule
