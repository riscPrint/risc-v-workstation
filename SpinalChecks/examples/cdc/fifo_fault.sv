`define CDC_FAULT
// Selected depth-four FIFO, with explicit source/destination event enables.
// Compile with -DCDC_FAULT for the incorrect full condition.
module cdc_fifo(input clk, reset, source_tick, destination_tick, push, pop,
 input [7:0] data_in, input [2:0] forward_choice, reverse_choice,
 output ready, valid, output [7:0] data_out);
 reg [2:0] write_pointer, read_pointer;
 reg [7:0] memory [0:3];
 wire [2:0] write_gray = write_pointer ^ (write_pointer >> 1);
 wire [2:0] read_gray = read_pointer ^ (read_pointer >> 1);
 wire [2:0] write_sync, read_sync;
 rvw_cdc_sample #(3) f(clk,reset,destination_tick,write_gray,forward_choice,write_sync);
 rvw_cdc_sample #(3) r(clk,reset,source_tick,read_gray,reverse_choice,read_sync);
`ifdef CDC_FAULT
 assign ready = 1;
`else
 assign ready = write_gray != (read_sync ^ 3'b110);
`endif
 assign valid = read_gray != write_sync;
 assign data_out = memory[read_pointer[1:0]];
 always @(posedge clk) begin
   if (reset) begin write_pointer <= 0; read_pointer <= 0; end
   else begin
     if (source_tick && push && ready) begin
       memory[write_pointer[1:0]] <= data_in;
       write_pointer <= write_pointer + 1;
     end
     if (destination_tick && pop && valid) read_pointer <= read_pointer + 1;
   end
 end
endmodule

`undef CDC_FAULT
