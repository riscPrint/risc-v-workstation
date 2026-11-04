package cpu_vip;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 import "DPI-C" function int rvw_uvm_check(input longint unsigned data[]);
 import "DPI-C" function string rvw_uvm_error();
 class retirement extends uvm_sequence_item;
   `uvm_object_utils(retirement)
   longint unsigned values[19];
   function new(string name="retirement"); super.new(name); endfunction
 endclass
 class spike_scoreboard extends uvm_subscriber#(retirement);
   `uvm_component_utils(spike_scoreboard)
   int checked;
   function new(string name,uvm_component parent); super.new(name,parent); endfunction
   function void write(retirement t);
     int status=rvw_uvm_check(t.values);
     if(status==1) `uvm_fatal("SPIKE_MISMATCH",rvw_uvm_error())
     if(status!=0) `uvm_fatal("SPIKE_ERROR",rvw_uvm_error())
     checked++;
   endfunction
 endclass
 class capture_monitor extends uvm_component;
   `uvm_component_utils(capture_monitor)
   uvm_analysis_port#(retirement) ap;
   function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); endfunction
   task replay();
     string path;
     int fd, count, expected, rc;
     retirement t;
     if(!$value$plusargs("records=%s",path)) `uvm_fatal("INPUT","missing capture")
     fd=$fopen(path,"r"); if(!fd) `uvm_fatal("INPUT","cannot open capture")
     rc=$fscanf(fd,"%d",expected); if(rc!=1 || expected<1) `uvm_fatal("INPUT","invalid count")
     repeat(expected) begin
       t=new();
       foreach(t.values[i]) begin
         rc=$fscanf(fd,"%h",t.values[i]); if(rc!=1) `uvm_fatal("INPUT","truncated record")
       end
       if($test$plusargs("corrupt") && count==0) t.values[1]^=4;
       ap.write(t); count++; #1;
     end
     rc=$fscanf(fd,"%h",expected); if(rc==1) `uvm_fatal("INPUT","extra record data")
     $fclose(fd);
   endtask
 endclass
 class cpu_test extends uvm_test;
   `uvm_component_utils(cpu_test)
   capture_monitor m; spike_scoreboard sc;
   function new(string name="cpu_test",uvm_component parent=null); super.new(name,parent); endfunction
   function void build_phase(uvm_phase phase); m=new("m",this); sc=new("sc",this); endfunction
   function void connect_phase(uvm_phase phase); m.ap.connect(sc.analysis_export); endfunction
   function void end_of_elaboration_phase(uvm_phase phase);
     set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
   endfunction
   task run_phase(uvm_phase phase);
     phase.raise_objection(this); m.replay(); phase.drop_objection(this);
   endtask
   function void check_phase(uvm_phase phase);
     if(sc.checked<1) `uvm_fatal("CHECK","no retirements")
     $display("RVW_CPU_CHECKED %0d",sc.checked);
   endfunction
   function void report_phase(uvm_phase phase); $display("RVW_CPU_DONE"); endfunction
 endclass
endpackage
// Profile and memory setup are generated from captured ELF and platform inputs.
`include "cpu_top.svh"
