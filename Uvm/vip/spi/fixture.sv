// Digital wire-loopback DUT. Seed the driver sequence with the simulator seed.
module spi_loopback(spi_if b);
  assign b.miso=b.mosi ^ $test$plusargs("buggy");
endmodule
