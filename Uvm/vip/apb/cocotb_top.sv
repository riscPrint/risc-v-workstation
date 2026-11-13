module cocotb_top(
  input logic clk, reset_n, psel, penable, pwrite,
  input logic [31:0] paddr, pwdata,
  input logic [3:0] pstrb,
  input logic [2:0] pprot,
  output logic pready, pslverr,
  output logic [31:0] prdata
);
  apb_if b(clk);
  assign b.reset_n=reset_n;
  assign b.psel=psel; assign b.penable=penable; assign b.pwrite=pwrite;
  assign b.paddr=paddr; assign b.pwdata=pwdata;
  assign b.pstrb=pstrb; assign b.pprot=pprot;
  assign pready=b.pready; assign pslverr=b.pslverr; assign prdata=b.prdata;
  apb_ram dut(b);
endmodule
