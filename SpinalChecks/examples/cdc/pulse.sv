// A single source pulse becomes a retained toggle before synchronization.
module cdc_pulse(input clk, reset, source_tick, destination_tick, pulse,
 input [2:0] forward_choice, output captured);
 reg toggle, seen;
 wire received;
 always @(posedge clk) begin
   if (reset) begin toggle <= 0; seen <= 0; end
   else begin
     if (source_tick && pulse) toggle <= ~toggle;
     if (destination_tick) seen <= received;
   end
 end
`ifdef CDC_FAULT
 rvw_cdc_sample f(clk,reset,destination_tick,pulse,forward_choice[0],received);
`else
 rvw_cdc_sample f(clk,reset,destination_tick,toggle,forward_choice[0],received);
`endif
 assign captured = destination_tick && (received != seen);
endmodule
