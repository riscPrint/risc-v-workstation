module top;
 int value;
 covergroup cg;
  cp: coverpoint value { bins path = (0 => 1 => 2); }
 endgroup
 cg coverage = new;
 initial begin
  value=0; coverage.sample();
  value=1; coverage.sample();
  value=2; coverage.sample();
  if(coverage.get_inst_coverage()!=100.0) $fatal(1,"TRANSITION_COVERAGE");
  $display("RVW_PROBE_DONE"); $finish;
 end
endmodule
