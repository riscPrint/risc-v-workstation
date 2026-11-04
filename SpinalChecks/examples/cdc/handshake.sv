// One outstanding transfer. Toggle request and returned acknowledgement.
// Compile with -DCDC_FAULT to violate data stability while busy.
module cdc_handshake(input clk, reset, source_tick, destination_tick, push, pop,
 input [7:0] data_in, input [2:0] forward_choice, reverse_choice,
 output ready, valid, output [7:0] data_out);
 reg request, acknowledgement;
 reg [7:0] held;
 wire request_sync, acknowledgement_sync;
 rvw_cdc_sample f(clk,reset,destination_tick,request,forward_choice[0],request_sync);
 rvw_cdc_sample r(clk,reset,source_tick,acknowledgement,reverse_choice[0],acknowledgement_sync);
 assign ready = request == acknowledgement_sync;
 assign valid = request_sync != acknowledgement;
 assign data_out = held;
 always @(posedge clk) begin
   if (reset) begin request <= 0; acknowledgement <= 0; held <= 0; end
   else begin
`ifdef CDC_FAULT
     if (source_tick) held <= data_in;
`endif
     if (source_tick && push && ready) begin held <= data_in; request <= ~request; end
     if (destination_tick && pop && valid) acknowledgement <= request_sync;
   end
 end
endmodule
