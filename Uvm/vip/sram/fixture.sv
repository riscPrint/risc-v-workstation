module sram_fixture(sram_if b);
  bit [31:0] memory[16];bit [31:0] response_q;bit valid_q;
  assign b.valid=valid_q;
  assign b.response=response_q^32'($test$plusargs("buggy"));
  always @(posedge b.clk)begin
    if(!b.reset_n)begin foreach(memory[i])memory[i]<=0;valid_q<=0;response_q<=0;end
    else begin
      valid_q<=b.enable && !b.write;
      if(b.enable && b.address<16)begin
        if(b.write)begin for(int i=0;i<4;i++)if(b.mask[i])memory[b.address][8*i+:8]<=b.data[8*i+:8];end
        else response_q<=memory[b.address];
      end
    end
  end
endmodule
