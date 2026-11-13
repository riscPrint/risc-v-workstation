class item;
 rand bit [31:0] data;
endclass
class stimulus;
 task start_item(item t); #5; endtask
 task finish_item(item t); #5; endtask
 virtual task run;
  item t;
  bit [31:0] previous;
  bit changed;
  for(int i=0;i<40;i++) begin
   t=new;
   start_item(t);
   if(!t.randomize()) $fatal;
   if(i>=8 && t.data!=previous) changed=1;
   previous=t.data;
   finish_item(t);
  end
  $display("changed=%0d",changed);
  if(!changed) $fatal(1,"random data did not change");
 endtask
endclass
module top;
 stimulus s;
 initial begin s=new; s.run; $finish; end
endmodule
