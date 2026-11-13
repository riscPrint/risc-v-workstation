// Two input registers. Combinational outputs expose the pre-edge reference.
module gpio_fixture(gpio_if b);
  bit [7:0] sync0,sync1,previous;
  wire [7:0] resolved_pins=(b.output_value&b.direction)|(b.external_value&~b.direction);
  always @(posedge b.clk) begin
    if(!b.reset_n) begin sync0<=0; sync1<=0; previous<=0; end
    else begin sync0<=resolved_pins; sync1<=sync0; previous<=sync1; end
  end
  assign b.sampled=b.reset_n ? sync1 : 0;
  assign b.irq=!b.reset_n ? 0 : ((sync1&~previous&b.rising_mask)|(~sync1&previous&b.falling_mask)|
    (sync1&b.high_mask)|(~sync1&b.low_mask)) ^ (8'($test$plusargs("buggy")));
endmodule
