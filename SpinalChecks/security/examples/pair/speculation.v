// Small fixed-program fetch/resolve model. This is not a general RISC-V core.
module SeededPipeline #(parameter SEED=1, parameter LEAK=0)(
 input clk,reset,input [31:0] secret,output reg [34:0] arch,output reg [8:0] cache);
localparam [31:0] BRANCH=32'h00000463; // beq x0,x0,+8
localparam [31:0] LOAD=32'h00052083;   // lw x1,0(x10), wrong path
localparam [31:0] NOP=32'h00000013;    // addi x0,x0,0
reg [1:0] pc,execute_pc;
reg [31:0] instruction;
reg valid;
function [31:0] rom;
 input [1:0] address;
 begin case(address) 0:rom=BRANCH;1:rom=LOAD;default:rom=NOP;endcase end
endfunction
wire [31:0] fetched=rom(pc);
wire taken=valid && instruction==BRANCH;
wire [7:0] address=(secret >> SEED) ^ (8'h53 * SEED);
always @(posedge clk) begin
 if(reset)begin pc<=0;execute_pc<=0;instruction<=NOP;valid<=0;arch<=0;cache<=0;end
 else begin
  // The safe version blocks the younger load at branch resolution.
  cache <= fetched==LOAD && (LEAK || !taken) ? {1'b1,address} : 9'b0;
  arch <= valid ? {1'b1,execute_pc,instruction} : 35'b0;
  if(taken)begin pc<=2;valid<=0;instruction<=NOP;end
  else begin
   instruction<=fetched;execute_pc<=pc;valid<=1;
   if(pc!=3)pc<=pc+1;
  end
 end
end
endmodule

module Seed1Safe(input clk,reset,input [31:0] secret,output [34:0] arch,output [8:0] cache);
SeededPipeline #(.SEED(1),.LEAK(0)) core(clk,reset,secret,arch,cache);
endmodule
module Seed1Leaky(input clk,reset,input [31:0] secret,output [34:0] arch,output [8:0] cache);
SeededPipeline #(.SEED(1),.LEAK(1)) core(clk,reset,secret,arch,cache);
endmodule
module Seed7Safe(input clk,reset,input [31:0] secret,output [34:0] arch,output [8:0] cache);
SeededPipeline #(.SEED(7),.LEAK(0)) core(clk,reset,secret,arch,cache);
endmodule
module Seed7Leaky(input clk,reset,input [31:0] secret,output [34:0] arch,output [8:0] cache);
SeededPipeline #(.SEED(7),.LEAK(1)) core(clk,reset,secret,arch,cache);
endmodule
