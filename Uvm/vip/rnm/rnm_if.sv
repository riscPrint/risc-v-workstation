// Real-number boundary stub. Valid/known must accompany every real sample.
interface rnm_if(input bit clk);
  real value;
  bit valid,known;
endinterface
