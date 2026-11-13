module ahb_ram(ahb_if b);
  byte unsigned memory[256];
  bit pending, wr, first_error;
  bit [31:0] address;
  bit [2:0] size;
  int remaining;
  assign b.hready=!pending || (remaining==0 && (address<256 || first_error));
  assign b.hresp=pending && remaining==0 && address>=256;
  always_comb begin
    b.hrdata=0;
    if(address<256)
      for(int i=0;i<4;i++) b.hrdata[8*i+:8]=memory[(address & ~3)+i];
    if($test$plusargs("buggy")) b.hrdata^=32'h01010101;
  end
  always @(posedge b.clk) begin
    if(!b.reset_n) begin
      foreach(memory[i]) memory[i]<=0;
      pending<=0; first_error<=0; remaining<=0;
    end else begin
      if(pending) begin
        if(remaining>0) remaining<=remaining-1;
        else if(b.hresp && !b.hready) first_error<=1;
        else if(b.hready && wr && !b.hresp)
          for(int i=0;i<(1<<size);i++) memory[address+i]<=b.hwdata[8*((address%4)+i)+:8];
      end
      if(b.hready) begin
        pending<=b.hsel && b.htrans[1]; first_error<=0;
        if(b.hsel && b.htrans[1]) begin
          address<=b.haddr; wr<=b.hwrite; size<=b.hsize;
          remaining<=$test$plusargs("bad_manager") ? 1 : $urandom_range(0,3);
        end
      end
    end
  end
endmodule
