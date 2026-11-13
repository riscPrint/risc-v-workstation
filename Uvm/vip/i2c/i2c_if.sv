interface i2c_if(input bit clk);
  bit reset_n;
  bit manager_scl_low,manager_sda_low,sub_scl_low,sub_sda_low;
  // Split enables implement pull-ups and wired-AND resolution on two-state backends.
  wire scl=!(manager_scl_low|sub_scl_low);
  wire sda=!(manager_sda_low|sub_sda_low);
endinterface
module i2c_checker(i2c_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    !$isunknown({b.scl,b.sda})) else $fatal(1,"I2C_UNKNOWN_LINE");
endmodule
