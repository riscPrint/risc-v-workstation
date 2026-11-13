// The same logical words in one physical vector.
module Packed(input clk,reset,we,input [2:0] wa,ra,input [7:0] wd,output [7:0] rd);
reg [63:0] storage;
reg [7:0] written;
always @(posedge clk) begin
  if(reset) written<=0;
  else if(we) begin storage[wa*8+:8]<=wd; written[wa]<=1; end
end
assign rd=written[ra] ? storage[ra*8+:8] : 8'd0;
endmodule
