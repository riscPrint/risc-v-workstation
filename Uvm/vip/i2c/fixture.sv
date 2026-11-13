// Seeded ACK target. +buggy changes ACK into NACK. Not a register device.
module i2c_target(i2c_if b);
  int bits; bit active,old_scl=1,old_sda=1;
  always @(posedge b.clk) begin
    if(!b.reset_n) begin bits=0; active=0; b.sub_sda_low=0; end
    else begin
      if(old_scl && b.scl && old_sda!=b.sda) begin active=!b.sda; bits=0; end
      if(active && !old_scl && b.scl) bits++;
      if(old_scl && !b.scl) begin
        if(bits==9) bits=0;
        b.sub_sda_low=active && bits==8 && !$test$plusargs("buggy");
      end
    end
    old_scl=b.scl; old_sda=b.sda;
  end
endmodule
