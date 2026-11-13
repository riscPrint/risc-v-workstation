`timescale 1ns/1ps
module apb_manager(
input clk,reset_n,go,
input [31:0] request_address,
output reg done,
output reg [31:0] result,
output wire psel,
output wire penable,
output wire [31:0] paddr,
output wire pwrite,
output wire [31:0] pwdata,
output wire [3:0] pstrb,
output wire [2:0] pprot,
input wire pready,
input wire [31:0] prdata,
input wire pslverr
);
int stage;
 always @(posedge clk)begin
   if(!reset_n)begin stage<=0;done<=0;result<=0;end
   else case(stage)
     0:if(go)stage<=1;
     1:if(pready)stage<=2;
     2:if(pready)begin result<=prdata;done<=1;stage<=3;end
   endcase
 end
assign psel=stage==1 || stage==2;
assign penable=stage==2;
assign paddr=request_address;
assign pwrite=0;
assign pwdata=0;
assign pstrb=15;
assign pprot=0;
endmodule
