module top;
 class item;
  randc bit [3:0] value;
 endclass
 initial begin
  item t = new;
  bit [15:0] seen = 0;
  repeat(16) begin
   if(!t.randomize()) $fatal(1,"RANDOMIZE_FAILED");
   if(seen[t.value]) $fatal(1,"RANDC_REPEATED");
   seen[t.value]=1;
  end
  if(seen != '1) $fatal(1,"RANDC_MISSING");
  $display("RVW_PROBE_DONE"); $finish;
 end
endmodule
