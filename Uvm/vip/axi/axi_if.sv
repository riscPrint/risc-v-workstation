// Bounded AXI4 profile: 32-bit data/address, 4-bit IDs, aligned transfers.
interface axi_if(input bit clk);
  bit reset_n=0;
  bit awvalid,awready,wvalid,wready,bvalid,bready,arvalid,arready,rvalid,rready;
  bit [31:0] awaddr,araddr,wdata,rdata;
  bit [3:0] awid,arid,bid,rid,wstrb,awcache,arcache;
  bit [7:0] awlen,arlen;
  bit [2:0] awsize=2,arsize=2,awprot,arprot;
  bit [1:0] awburst=1,arburst=1,bresp,rresp;
  bit awlock,arlock,wlast,rlast;
endinterface

module axi_checker #(parameter bit LITE=0)(axi_if b);
  assert property(@(posedge b.clk) !b.reset_n |->
    !(b.awvalid || b.wvalid || b.bvalid || b.arvalid || b.rvalid)) else $fatal(1,"AXI_RESET_VALID");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.awvalid && !b.awready |=> b.awvalid && $stable({b.awaddr,b.awid,b.awlen,b.awsize,b.awburst,b.awlock,b.awprot,b.awcache})) else $fatal(1,"AXI_STABLE_AW");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.arvalid && !b.arready |=> b.arvalid && $stable({b.araddr,b.arid,b.arlen,b.arsize,b.arburst,b.arlock,b.arprot,b.arcache})) else $fatal(1,"AXI_STABLE_AR");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.wvalid && !b.wready |=> b.wvalid && $stable({b.wdata,b.wstrb,b.wlast})) else $fatal(1,"AXI_STABLE_W");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.bvalid && !b.bready |=> b.bvalid && $stable({b.bid,b.bresp})) else $fatal(1,"AXI_STABLE_B");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.rvalid && !b.rready |=> b.rvalid && $stable({b.rid,b.rresp,b.rdata,b.rlast})) else $fatal(1,"AXI_STABLE_R");
endmodule
