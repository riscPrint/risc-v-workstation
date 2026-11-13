// Declared SHA-256 instruction-unit timing contract. No instruction decoder.
module ShaTiming #(parameter LEAK=0)(input clk,reset,start,input [31:0] operand,
 output [31:0] result,output reg busy,done);
reg [1:0] phase;
assign result={operand[6:0],operand[31:7]} ^ {operand[17:0],operand[31:18]} ^ (operand >> 3);
always @(posedge clk) begin
 if(reset)begin busy<=0;done<=0;phase<=0;end
 else begin
  done<=0;
  if(!busy)begin if(start)begin busy<=1;phase<=0;end end
  else if(phase==(LEAK && operand[0] ? 2 : 1))begin busy<=0;done<=1;end
  else phase<=phase+1;
 end
end
endmodule
module ShaFixed(input clk,reset,start,input [31:0] operand,output [31:0] result,output busy,done);
ShaTiming #(.LEAK(0)) unit(clk,reset,start,operand,result,busy,done);
endmodule
module ShaLeaky(input clk,reset,start,input [31:0] operand,output [31:0] result,output busy,done);
ShaTiming #(.LEAK(1)) unit(clk,reset,start,operand,result,busy,done);
endmodule
