interface tilelink_if(input bit clk);
  bit reset_n;
  bit a_valid,a_ready,d_valid,d_ready;
  bit [2:0] a_opcode,a_param,a_size,d_opcode,d_size;
  bit [1:0] d_param;
  bit [3:0] a_source,d_source,a_mask;
  bit [31:0] a_address,a_data,d_data;
  bit a_corrupt,d_denied,d_corrupt,d_sink;
endinterface

// TileLink does not require AXI-style stability for an unaccepted beat.
// Message and source checks live in the passive monitor.
module tilelink_checker(tilelink_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.d_valid && b.d_opcode==1 && b.d_denied |-> b.d_corrupt)
    else $fatal(1,"TL_D_CORRUPT");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.d_valid && b.d_opcode!=1 |-> !b.d_corrupt)
    else $fatal(1,"TL_D_CORRUPT");
endmodule
