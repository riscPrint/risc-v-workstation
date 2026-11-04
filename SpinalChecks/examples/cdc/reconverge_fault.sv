`define CDC_FAULT
// Both output bits must represent the same source event.
module cdc_reconverge(input clk, reset, source_tick, destination_tick, launch,
 input [2:0] forward_choice, output [1:0] pair);
 reg level;
 always @(posedge clk) begin
   if (reset) level <= 0;
   else if (source_tick && launch) level <= ~level;
 end
 rvw_cdc_sample a(clk,reset,destination_tick,level,forward_choice[0],pair[0]);
`ifdef CDC_FAULT
 rvw_cdc_sample b(clk,reset,destination_tick,level,forward_choice[1],pair[1]);
`else
 assign pair[1] = pair[0];
`endif
endmodule

`undef CDC_FAULT
