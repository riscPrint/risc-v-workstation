module top;bit clk=0;always #5 clk=~clk;ethernet_if bus(clk);ethernet_bridge_fixture dut(bus);endmodule
