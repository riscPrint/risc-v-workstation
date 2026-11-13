interface stress_if(input bit clk);
  bit reset_n,valid,ready,response,write,error;bit [3:0] source,txn;bit [1:0] qos;
  bit [31:0] address;bit [63:0] data,observed_data;
endinterface
