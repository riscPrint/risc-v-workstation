// Optional semantic transaction bridge. No PCIe wire encoding or PHY.
interface pcie_if(input bit clk);
  bit reset_n,valid,ready,write;bit [7:0] tag;
  bit [63:0] address;bit [31:0] data;bit [2:0] length;
endinterface
