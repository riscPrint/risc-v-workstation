package vex_sv_test;
 import uvm_pkg::*; import rvw_cpu_pkg::*;
 `include "uvm_macros.svh"
 cpu_memory ram;
 class vex_program extends uvm_test;
  `uvm_component_utils(vex_program)
  cpu_env env;
  virtual rvw_cpu_if vif;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void build_phase(uvm_phase phase);
   env=cpu_env::type_id::create("env",this);
   if(!uvm_config_db#(virtual rvw_cpu_if)::get(this,"","vif",vif)) `uvm_fatal("BINDING","missing CPU interface")
  endfunction
  function void end_of_elaboration_phase(uvm_phase phase);
   set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
  endfunction
  task run_phase(uvm_phase phase);
   string image;
   longint unsigned tohost;
   bit done=0;
   phase.raise_objection(this);
   if(!$value$plusargs("image=%s",image) || !$value$plusargs("tohost=%h",tohost))
    `uvm_fatal("IMAGE","image and tohost required")
   ram.base='h80000000; ram.size='h1000000; ram.max_wait=0;
   ram.preload(image);
   env.vseqr.controls.reset();
   repeat(10000) begin
    @(posedge vif.clk); #1;
    if(vif.rvfi_valid && vif.retirement[8]!=0 && vif.retirement[6]==tohost) begin
     if(vif.retirement[8]!=15 || vif.retirement[10]!=1) `uvm_fatal("TOHOST","program failed")
     @(posedge vif.clk); done=1; break;
    end
   end
   if(!done) `uvm_fatal("CPU_WATCHDOG","no checked tohost store")
   phase.drop_objection(this);
  endtask
  function void report_phase(uvm_phase phase);
   uvm_report_server server=uvm_report_server::get_server();
   if(server.get_severity_count(UVM_ERROR)==0 && server.get_severity_count(UVM_FATAL)==0 && env.scoreboard.checks>0)
    $display("RVW_UVM_DONE vex_program checks=%0d",env.scoreboard.checks);
  endfunction
 endclass
endpackage
module top;
 import uvm_pkg::*; import rvw_cpu_pkg::*; import vex_sv_test::*;
 bit clk=0; always #5 clk=~clk;
 rvw_cpu_if bus(clk);
 bit i_ready, i_valid, i_error, d_ready, d_valid, d_error;
 bit [31:0] i_data, d_data;
 `include "core_binding.svh"
 // Both buses use the same independent memory. Fixed one-cycle response.
 initial begin
  bit fetch, read_reply;
  bit [31:0] instruction, data;
  bit fetch_error, data_error;
  wait(ram!=null);
  forever begin
   @(posedge clk);
   fetch=bus.reset_n && core.iBus_cmd_valid && i_ready;
   read_reply=bus.reset_n && core.dBus_cmd_valid && d_ready && !core.dBus_cmd_payload_wr;
   if(fetch)
    ram.access(bus,1,0,core.iBus_cmd_payload_pc,0,15,instruction,fetch_error);
   if(bus.reset_n && core.dBus_cmd_valid && d_ready)
    ram.access(bus,0,core.dBus_cmd_payload_wr,core.dBus_cmd_payload_address & 32'hfffffffc,
      core.dBus_cmd_payload_data,core.dBus_cmd_payload_mask,data,data_error);
   @(negedge clk);
   i_valid=fetch; d_valid=read_reply;
   i_data=instruction; i_error=fetch_error; d_data=data; d_error=data_error;
   i_ready=bus.reset_n; d_ready=bus.reset_n;
  end
 end
 `include "spike_setup.svh"
 initial begin #200000; $fatal(1,"SV_CPU_WATCHDOG"); end
endmodule
