module top;bit clk=0;always #5 clk=~clk;rnm_if bus(clk);rnm_stub_fixture dut(bus);endmodule
