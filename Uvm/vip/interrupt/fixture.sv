module interrupt_fixture(interrupt_if b);
  assign b.observed=b.levels^8'($test$plusargs("buggy"));
endmodule
