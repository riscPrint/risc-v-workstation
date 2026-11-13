`timescale 1ns/1ps
// Project pins carry APB4 semantics. No protocol is inferred from their names.
module custom_endpoint(
 input tick, clear_n, request, access_phase, store,
 input [31:0] location, write_value,
 input [3:0] lanes,
 input [2:0] protection,
 input corrupt,
 output done, fault,
 output [31:0] read_value
);
 reg [31:0] words [0:3];
 reg [1:0] waits;
 integer i;
 assign done = clear_n && waits == 0;
 assign fault = location >= 16;
 assign read_value = (fault ? 32'b0 : words[location[3:2]]) ^
                     ((corrupt && !store) ? 32'b1 : 32'b0);
 always @(posedge tick) begin
  if (!clear_n) begin
   waits <= 0;
   for (i=0; i<4; i=i+1) words[i] <= 0;
  end else if (request && !access_phase) waits <= 2;
  else if (request && access_phase) begin
   if (waits != 0) waits <= waits - 1'b1;
   else if (store && !fault)
    for (i=0; i<4; i=i+1)
     if (lanes[i]) words[location[3:2]][8*i +: 8] <= write_value[8*i +: 8];
  end
 end
endmodule
