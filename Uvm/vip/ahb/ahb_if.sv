interface ahb_if(input bit clk);
  logic reset_n=0, hsel=1, hwrite=0, hmastlock=0;
  logic [1:0] htrans=0;
  logic [31:0] haddr=0, hwdata=0, hrdata;
  logic [2:0] hsize=2, hburst=0;
  logic [3:0] hprot=3;
  logic hready, hresp;
endinterface

module ahb_checker(ahb_if b);
  bit pending, writing;
  bit error_first;
  always @(posedge b.clk) begin
    if(!b.reset_n) begin pending<=0; writing<=0; error_first<=0; end
    else begin
      if(b.hresp && !pending) $fatal(1,"AHB_ERROR_WITHOUT_TRANSFER");
      if(b.hresp && b.hready && !error_first) $fatal(1,"AHB_ERROR_FIRST");
      if(error_first && !(b.hresp && b.hready)) $fatal(1,"AHB_ERROR_SECOND");
      error_first<=b.hresp && !b.hready;
      if(b.hready) begin pending<=b.hsel && b.htrans[1]; writing<=b.hwrite; end
      if(b.hready && b.hsel && b.htrans[1]) begin
        if(b.hsize>2 || (b.haddr & ((1<<b.hsize)-1))!=0) $fatal(1,"AHB_ALIGNMENT_SIZE");
      end
    end
  end
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    !b.hready && !b.hresp && b.htrans[1] |=>
    $stable({b.hsel,b.htrans,b.haddr,b.hwrite,b.hsize,b.hburst,b.hprot,b.hmastlock}))
    else $fatal(1,"AHB_ADDRESS_STABLE");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    !b.hready && pending && writing |=> $stable(b.hwdata))
    else $fatal(1,"AHB_DATA_STABLE");
endmodule
