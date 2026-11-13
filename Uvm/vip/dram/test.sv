module top;
  bit clk=0;always #5 clk=~clk;
  dram_if bus(clk);dram_bridge_fixture dut(bus);
endmodule
