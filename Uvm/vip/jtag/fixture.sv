module jtag_fixture(jtag_if b);
  assign b.tdo=b.tdi^$test$plusargs("buggy");
endmodule
