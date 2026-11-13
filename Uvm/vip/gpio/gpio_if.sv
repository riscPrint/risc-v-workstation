interface gpio_if(input bit clk);
  bit reset_n;
  bit [7:0] external_value,direction,output_value;
  logic [7:0] sampled,irq;
  bit [7:0] rising_mask=1,falling_mask=2,high_mask=4,low_mask=8;
endinterface
module gpio_checker(gpio_if b);
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    !$isunknown({b.sampled,b.irq})) else $fatal(1,"GPIO_UNKNOWN_PIN");
endmodule
