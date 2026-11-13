// Seeded bounded DUT, with +buggy read corruption.
module apb_ram(apb_if b);
  bit [31:0] memory[4];
  int remaining;
  assign b.pready=remaining==0;
  assign b.pslverr=b.paddr>=16 || b.paddr[1:0]!=0;
  assign b.prdata=(b.pslverr ? 0 : memory[b.paddr>>2]) ^ ($test$plusargs("buggy") ? 1 : 0);
  always @(posedge b.clk) begin
    if(!b.reset_n) begin
      foreach(memory[i]) memory[i]<=0;
      remaining<=0;
    end else if(b.psel && !b.penable) remaining<=$urandom_range(0,3);
    else if(b.psel && b.penable) begin
      if(remaining>0) remaining<=remaining-1;
      else if(b.pwrite && !b.pslverr)
        for(int i=0;i<4;i++) if(b.pstrb[i]) memory[b.paddr>>2][8*i+:8]<=b.pwdata[8*i+:8];
    end
  end
endmodule
