`define CDC_FAULT
// Destination release waits for two destination events after source release.
module cdc_reset(input clk, reset, source_tick, destination_tick,
 output reg source_up, destination_up);
 reg first;
 always @(posedge clk) begin
   if (reset) begin source_up <= 0; first <= 0; destination_up <= 0; end
   else begin
     if (source_tick) source_up <= 1;
     if (destination_tick) begin
       first <= source_up;
`ifdef CDC_FAULT
       destination_up <= 1;
`else
       destination_up <= first;
`endif
     end
   end
 end
endmodule

`undef CDC_FAULT
