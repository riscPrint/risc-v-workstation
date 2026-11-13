`timescale 1ns/1ps
module bus_top(
input clk,reset_n,buggy,
input [31:0] salt,
input wire  axi_awvalid,
output wire  axi_awready,
input wire  axi_wvalid,
output wire  axi_wready,
output wire  axi_bvalid,
input wire  axi_bready,
input wire  axi_arvalid,
output wire  axi_arready,
output wire  axi_rvalid,
input wire  axi_rready,
input wire [31:0] axi_awaddr,
input wire [31:0] axi_araddr,
input wire [31:0] axi_wdata,
output wire [31:0] axi_rdata,
input wire [3:0] axi_awid,
input wire [3:0] axi_arid,
output wire [3:0] axi_bid,
output wire [3:0] axi_rid,
input wire [3:0] axi_wstrb,
input wire [3:0] axi_awcache,
input wire [3:0] axi_arcache,
input wire [7:0] axi_awlen,
input wire [7:0] axi_arlen,
input wire [2:0] axi_awsize,
input wire [2:0] axi_arsize,
input wire [2:0] axi_awprot,
input wire [2:0] axi_arprot,
input wire [1:0] axi_awburst,
input wire [1:0] axi_arburst,
output wire [1:0] axi_bresp,
output wire [1:0] axi_rresp,
input wire  axi_awlock,
input wire  axi_arlock,
input wire  axi_wlast,
output wire  axi_rlast,
input wire  tl_a_valid,
output wire  tl_a_ready,
output wire  tl_d_valid,
input wire  tl_d_ready,
input wire [2:0] tl_a_opcode,
input wire [2:0] tl_a_param,
input wire [2:0] tl_a_size,
output wire [2:0] tl_d_opcode,
output wire [2:0] tl_d_size,
output wire [1:0] tl_d_param,
input wire [3:0] tl_a_source,
output wire [3:0] tl_d_source,
input wire [3:0] tl_a_mask,
input wire [31:0] tl_a_address,
input wire [31:0] tl_a_data,
output wire [31:0] tl_d_data,
input wire  tl_a_corrupt,
output wire  tl_d_denied,
output wire  tl_d_corrupt,
output wire  tl_d_sink
);
assign axi_awready=1;
assign axi_wready=1;
assign axi_bvalid=0;
assign axi_bid=0;
assign axi_bresp=0;
assign axi_arready=1;
assign axi_rvalid=reset_n && axi_arvalid;
assign axi_rid=axi_arid;
assign axi_rresp=0;
assign axi_rdata=axi_araddr ^ salt ^ {31'b0,buggy};
assign axi_rlast=1;
assign tl_a_ready=1;
assign tl_d_valid=reset_n && tl_a_valid;
assign tl_d_opcode=1;
assign tl_d_param=0;
assign tl_d_size=tl_a_size;
assign tl_d_source=tl_a_source;
assign tl_d_data=tl_a_address ^ salt ^ {31'b0,buggy};
assign tl_d_denied=0;
assign tl_d_corrupt=0;
assign tl_d_sink=0;
endmodule
