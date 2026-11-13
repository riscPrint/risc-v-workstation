module wishbone_ram(wishbone_if b);
  bit [31:0] memory[16];int delay_cycles;
  assign b.err=b.cyc && b.stb && delay_cycles==0 && (b.adr>=64 || b.adr[1:0]!=0);
  assign b.ack=b.cyc && b.stb && delay_cycles==0 && !b.err;
  assign b.dat_r=(b.adr<64 ? memory[b.adr>>2] : 0)^32'($test$plusargs("buggy"));
  always @(posedge b.clk) begin
    if(!b.reset_n)begin foreach(memory[i])memory[i]<=0;delay_cycles<=0;end
    else if(!b.cyc || !b.stb)delay_cycles<=$urandom_range(0,3);
    else if(delay_cycles>0)delay_cycles<=delay_cycles-1;
    else if(b.ack && b.we)for(int i=0;i<4;i++)if(b.sel[i])memory[b.adr>>2][8*i+:8]<=b.dat_w[8*i+:8];
  end
endmodule
