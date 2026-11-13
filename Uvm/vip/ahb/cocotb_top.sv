module cocotb_top(
  input logic clk, reset_n, hsel, hwrite, hmastlock,
  input logic [1:0] htrans,
  input logic [31:0] haddr, hwdata,
  input logic [2:0] hsize, hburst,
  input logic [3:0] hprot,
  output logic hready, hresp,
  output logic [31:0] hrdata
);
  ahb_if b(clk);
  assign b.reset_n=reset_n; assign b.hsel=hsel; assign b.hwrite=hwrite;
  assign b.hmastlock=hmastlock; assign b.htrans=htrans;
  assign b.haddr=haddr; assign b.hwdata=hwdata; assign b.hsize=hsize;
  assign b.hburst=hburst; assign b.hprot=hprot;
  assign hready=b.hready; assign hresp=b.hresp; assign hrdata=b.hrdata;
  ahb_ram dut(b);
endmodule
