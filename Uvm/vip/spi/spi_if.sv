interface spi_if(input bit clk);
  bit reset_n,cs_n=1,sclk,mosi,miso;
  bit polarity,phase,lsb_first;
  int bits=8;
endinterface
module spi_checker(spi_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.cs_n |-> b.sclk==b.polarity) else $fatal(1,"SPI_IDLE_CLOCK");
endmodule
