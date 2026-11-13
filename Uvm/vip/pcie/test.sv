module top;bit clk=0;always #5 clk=~clk;pcie_if bus(clk);pcie_bridge_fixture dut(bus);endmodule
