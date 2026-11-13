// rvw.chi-like/1 event bridge. This is not an Arm CHI wire interface.
interface coherent_if(input bit clk);
  bit reset_n,valid,ready;bit [1:0] kind,op,node;bit [3:0] txn;
  bit [31:0] line;bit [63:0] data,observed_data;
endinterface
