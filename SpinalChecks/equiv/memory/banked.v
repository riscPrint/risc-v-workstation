// Eight logical words in two independent physical banks.
module Banked(input clk,reset,we,input [2:0] wa,ra,input [7:0] wd,output [7:0] rd);
reg [7:0] even_bank[0:3],odd_bank[0:3];
reg [3:0] even_valid,odd_valid;
always @(posedge clk) begin
  if(reset) begin even_valid<=0; odd_valid<=0; end
  else if(we) begin
    if(wa[0]) begin odd_bank[wa[2:1]]<=wd; odd_valid[wa[2:1]]<=1; end
    else begin even_bank[wa[2:1]]<=wd; even_valid[wa[2:1]]<=1; end
  end
end
assign rd=ra[0] ? (odd_valid[ra[2:1]] ? odd_bank[ra[2:1]] : 8'd0)
                : (even_valid[ra[2:1]] ? even_bank[ra[2:1]] : 8'd0);
endmodule
