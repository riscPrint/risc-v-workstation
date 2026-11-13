interface axis_if(input bit clk);
  logic reset_n=0, tvalid=0, tready, tlast=1;
  logic [31:0] tdata=0;
  logic [3:0] tkeep=15, tstrb=15, tuser=0;
  logic [1:0] tid=0, tdest=0;
endinterface
module axis_checker(axis_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.tvalid && !b.tready |=> b.tvalid && $stable({b.tdata,b.tkeep,b.tstrb,b.tlast,b.tid,b.tdest,b.tuser}))
    else $fatal(1,"AXIS_STABLE");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.tvalid |-> (b.tstrb & ~b.tkeep)==0) else $fatal(1,"AXIS_BYTE_QUALIFIER");
  assert property(@(posedge b.clk) !b.reset_n |-> !b.tvalid) else $fatal(1,"AXIS_RESET_VALID");
endmodule
