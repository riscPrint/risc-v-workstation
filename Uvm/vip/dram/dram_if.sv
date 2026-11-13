// Project bridge for a declared digital model. No DDR pin-level semantics.
interface dram_if(input bit clk);
  bit reset_n,valid,ready;
  bit [2:0] command; // ACT=0 PRE=1 RD=2 WR=3 REF=4
  int bank,row,column;
  bit [63:0] write_data,read_data;
  bit read_valid;
endinterface
