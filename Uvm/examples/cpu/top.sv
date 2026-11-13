package cpu_smoke_pkg;
 import uvm_pkg::*; import rvw_cpu_pkg::*;
 `include "uvm_macros.svh"
 cpu_memory shared_memory;
 class cpu_smoke extends uvm_test;
  `uvm_component_utils(cpu_smoke)
  cpu_env env;
  virtual rvw_cpu_if vif;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void build_phase(uvm_phase phase);
   env=cpu_env::type_id::create("env",this);
   if(!uvm_config_db#(virtual rvw_cpu_if)::get(this,"","vif",vif)) `uvm_fatal("BINDING","missing interface")
  endfunction
  function void end_of_elaboration_phase(uvm_phase phase);
   set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
  endfunction
  task run_phase(uvm_phase phase);
   string image;
   cpu_control_sequence controls=new(); controls.vif=vif;
   phase.raise_objection(this);
   env.memory.base=32'h80000000; env.memory.size=4096;
   if(!$value$plusargs("image=%s",image)) `uvm_fatal("IMAGE","missing ELF byte image")
   env.memory.preload(image);
   controls.reset();
   wait(env.scoreboard.checks==4);
   phase.drop_objection(this);
  endtask
  function void report_phase(uvm_phase phase);
   uvm_report_server server=uvm_report_server::get_server();
   if(server.get_severity_count(UVM_ERROR)==0 && server.get_severity_count(UVM_FATAL)==0 && env.scoreboard.checks==4)
    $display("RVW_UVM_DONE cpu_smoke checks=%0d",env.scoreboard.checks);
  endfunction
 endclass
endpackage
module top;
 import uvm_pkg::*; import rvw_cpu_pkg::*; import cpu_smoke_pkg::*;
 bit clk=0; always #5 clk=~clk;
 rvw_cpu_if bus(clk);
 bit request, grant, error;
 bit [31:0] address, instruction;
 longint unsigned values[19];
 bit valid;
 longint unsigned order;
 addi_core core(clk,bus.reset_n,grant,instruction,request,address,valid,order,values);
 always_comb begin
  bus.state_valid=1; bus.csr_count=0;
  foreach(bus.gpr_state[i]) bus.gpr_state[i]=core.registers[i];
  if($test$plusargs("corrupt_state")) bus.gpr_state[5]^=1;
  bus.rvfi_valid=valid; bus.rvfi_order=order; bus.retirement=values;
  if($test$plusargs("corrupt")) bus.retirement[5]=values[5]^1;
 end
 // The project wrapper owns this normalized instruction response handshake.
 initial begin
  wait(shared_memory!=null);
  forever begin
   @(negedge clk);
   if(request) begin
    shared_memory.access(bus,1,0,address,0,15,instruction,error);
    if(error) $fatal(1,"fetch error on normal fixture");
    @(negedge clk); grant=1;
    @(negedge clk); grant=0;
   end
  end
 end
 `include "spike_setup.svh"
 initial begin #10000; $fatal(1,"watchdog"); end
endmodule
