`timescale 1ns/1ps
module ahb_manager(
input clk,reset_n,go,
input [31:0] request_address,
output reg done,
output reg [31:0] result,
output wire hsel,
output wire [1:0] htrans,
output wire [31:0] haddr,
output wire hwrite,
output wire [2:0] hsize,
output wire [2:0] hburst,
output wire [3:0] hprot,
output wire hmastlock,
output wire [31:0] hwdata,
input wire [31:0] hrdata,
input wire hready,
input wire hresp
);
int stage;
 always @(posedge clk)begin
   if(!reset_n)begin stage<=0;done<=0;result<=0;end
   else case(stage)
     0:if(go)stage<=1;
     1:if(hready)stage<=2;
     2:if(hready)begin result<=hrdata;done<=1;stage<=3;end
   endcase
 end
assign hsel=stage==1;
assign htrans=stage==1 ? 2 : 0;
assign haddr=request_address;
assign hwrite=0;
assign hsize=2;
assign hburst=0;
assign hprot=3;
assign hmastlock=0;
assign hwdata=0;
endmodule
