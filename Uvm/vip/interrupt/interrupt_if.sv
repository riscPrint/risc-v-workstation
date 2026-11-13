interface interrupt_if(input bit clk);
  bit reset_n;logic [7:0] levels,observed;
endinterface
module interrupt_checker(interrupt_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    !$isunknown(b.observed)) else $fatal(1,"IRQ_UNKNOWN_OR_WIDE");
endmodule
