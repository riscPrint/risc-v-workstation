interface wishbone_if(input bit clk);
  bit reset_n,cyc,stb,we,ack,err;
  bit [31:0] adr,dat_w,dat_r;
  bit [3:0] sel=15;
endinterface
module wishbone_checker(wishbone_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    !(b.ack && b.err)) else $fatal(1,"WB_MULTIPLE_TERMINATION");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.stb |-> b.cyc) else $fatal(1,"WB_STROBE_WITHOUT_CYCLE");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.cyc && b.stb && !b.ack && !b.err |=> b.cyc && b.stb && $stable({b.we,b.adr,b.dat_w,b.sel}))
    else $fatal(1,"WB_UNSTABLE_REQUEST");
endmodule
