interface sram_if(input bit clk);
  bit reset_n,enable,write;
  bit [31:0] address,data,response;
  bit [3:0] mask=15;
  bit valid;
endinterface
module sram_checker(sram_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.enable |-> b.address<16) else $fatal(1,"MEM_ADDRESS");
endmodule
