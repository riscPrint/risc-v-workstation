// A bounded RV32I ADDI fixture. This is not a production CPU or an ISA suite.
module addi_core(input bit clk, reset_n, grant, input bit [31:0] instruction,
                 output bit request, output bit [31:0] address,
                 output bit valid, output longint unsigned order,
                 output longint unsigned values[19]);
 bit [31:0] registers[32];
 bit [31:0] pc;
 longint unsigned retired;
 bit [4:0] rd, rs1;
 bit [31:0] result;
 assign request=reset_n;
 assign address=pc;
 always @(posedge clk) begin
  valid<=0;
  if(!reset_n) begin
   pc<=32'h80000000; order<=0; retired<=0;
   foreach(registers[i]) registers[i]<=0;
   foreach(values[i]) values[i]<=0;
  end else if(grant) begin
   if(instruction[6:0]!=7'h13 || instruction[14:12]!=0) $fatal(1,"fixture supports ADDI only");
   rd=instruction[11:7]; rs1=instruction[19:15];
   result=registers[rs1]+32'($signed(instruction[31:20]));
   if(rd!=0) registers[rd]<=result;
   foreach(values[i]) values[i]<=0;
   values[0]<=pc; values[1]<=pc+4; values[2]<=instruction; values[3]<=3;
   values[4]<=rd; values[5]<=rd==0 ? 0 : result;
   values[13]<=rs1; values[14]<=registers[rs1];
   pc<=pc+4; valid<=1;
   order<=retired; retired<=retired+1;
  end
 end
endmodule
