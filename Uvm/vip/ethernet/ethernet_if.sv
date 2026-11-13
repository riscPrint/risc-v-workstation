// MAC client-byte stream. No preamble, padding, FCS or PHY.
interface ethernet_if(input bit clk);
  bit reset_n,valid,ready,last,error;byte unsigned data;
endinterface
