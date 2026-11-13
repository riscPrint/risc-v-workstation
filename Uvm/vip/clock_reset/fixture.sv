module clock_reset_fixture(clock_reset_if b);
  assign b.observed_clock=b.clock;
  assign b.observed_reset_n=$test$plusargs("buggy") ? b.clock : b.reset_n;
endmodule
