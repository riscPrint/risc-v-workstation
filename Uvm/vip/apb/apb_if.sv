// APB4 single-select, 32-bit data/address. PWAKEUP and user signals excluded.
interface apb_if(input bit clk);
  logic reset_n=0, psel=0, penable=0, pwrite=0;
  logic [31:0] paddr=0, pwdata=0, prdata;
  logic [3:0] pstrb=0;
  logic [2:0] pprot=0;
  logic pready, pslverr;
endinterface

module apb_checker(apb_if b);
  // PENABLE can be high with PSEL low when a different peripheral is selected.
  property setup_access;
    @(posedge b.clk) disable iff(!b.reset_n)
    b.psel && !b.penable |=> b.psel && b.penable;
  endproperty
  property wait_access;
    @(posedge b.clk) disable iff(!b.reset_n)
    b.psel && b.penable && !b.pready |=> b.psel && b.penable;
  endproperty
  property stable_control;
    @(posedge b.clk) disable iff(!b.reset_n)
    b.psel && (!b.penable || !b.pready) |=>
      $stable({b.paddr,b.pwrite,b.pstrb,b.pprot});
  endproperty
  property stable_data;
    @(posedge b.clk) disable iff(!b.reset_n)
    b.psel && b.pwrite && (!b.penable || !b.pready) |=> $stable(b.pwdata);
  endproperty
  property access_end;
    @(posedge b.clk) disable iff(!b.reset_n)
    b.psel && b.penable && b.pready |=> !b.psel || !b.penable;
  endproperty
  assert property(setup_access) else $fatal(1,"APB_PHASE setup");
  assert property(wait_access) else $fatal(1,"APB_PHASE wait");
  assert property(stable_control) else $fatal(1,"APB_STABLE control");
  assert property(stable_data) else $fatal(1,"APB_STABLE data");
  assert property(access_end) else $fatal(1,"APB_SETUP completion");
  assert property(@(posedge b.clk) disable iff(!b.reset_n)
    b.psel && !b.pwrite |-> b.pstrb==0) else $fatal(1,"APB_READ_STROBE");
  bit active;
  always @(posedge b.clk) begin
    if(!b.reset_n) active<=0;
    else begin
      if(b.psel && b.penable && !active) $fatal(1,"APB_SETUP missing");
      active<=b.psel && (!b.penable || !b.pready);
    end
  end
endmodule
