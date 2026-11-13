interface uart_if(input bit clk);
  bit reset_n,tx=1,rx=1;
  int cycles_per_bit=8,data_bits=8,stop_bits=1;
  // parity: 0 none, 1 even, 2 odd.
  int parity=0;
endinterface
module uart_checker(uart_if b);
  initial begin
    if(b.cycles_per_bit<4 || b.data_bits<5 || b.data_bits>9 || b.stop_bits<1 || b.stop_bits>2 || b.parity<0 || b.parity>2)
      $fatal(1,"UART_CONFIG");
  end
endmodule
