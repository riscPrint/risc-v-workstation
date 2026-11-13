// Projects implement the backend tasks with actual DUT and scoreboard activity.
package rvw_soc_sequences;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 virtual class backend extends uvm_object;
  function new(string name="backend"); super.new(name); endfunction
  pure virtual task reset();
  pure virtual task boot(output int checks);
  pure virtual task wait_cycles(input int count);
  pure virtual task irq(input bit [63:0] mask);
  pure virtual task wait_interrupt(input int cause, output int actual_cause, checks);
  pure virtual task inject_bus_error(input bit enable);
  pure virtual task transfer(input bit [31:0] address, output bit error, output int checks);
  pure virtual task start_traffic();
  pure virtual task traffic_pending(output bit pending);
  pure virtual task check_reset(output bit aborted, output int checks);
  pure virtual task stop_traffic();
 endclass
 class sequencer extends uvm_sequencer;
  `uvm_component_utils(sequencer)
  backend project;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
 endclass
 class scenario extends uvm_sequence;
  `uvm_object_utils(scenario)
  string mode="boot";
  int count=16,max_gap=8,reset_delay=3;
  bit [63:0] allowed_irqs=0;
  bit [31:0] error_address;
  function new(string name="scenario"); super.new(name); endfunction
  task body();
   sequencer sq;
   backend b;
   int checks,actual,cause;
   int causes[$];
   bit error,pending,aborted;
   if(!$cast(sq,m_sequencer) || sq.project==null)
    `uvm_fatal("SOC_PROJECT_BACKEND","project sequencer backend required")
   b=sq.project; checks=0;
   case(mode)
    "boot": begin b.reset(); b.boot(checks); end
    "interrupt_storm": begin
     for(int i=0;i<64;i++) if(allowed_irqs[i]) causes.push_back(i);
     if(causes.size()==0 || count<1 || max_gap<1)
      `uvm_fatal("SOC_IRQ_BOUNDS","causes and positive bounds required")
     for(int i=0;i<count;i++) begin
      int n;
      cause=causes[$urandom_range(causes.size()-1,0)];
      b.wait_cycles($urandom_range(max_gap,1)); b.irq(64'b1<<cause);
      b.wait_interrupt(cause,actual,n); b.irq(0);
      if(actual!=cause || n<1) `uvm_fatal("SOC_IRQ_CHECK","missing checked interrupt")
      checks+=n;
     end
    end
    "bus_error": begin
     b.inject_bus_error(1); b.transfer(error_address,error,checks); b.inject_bus_error(0);
     if(!error) `uvm_fatal("SOC_BUS_ERROR","injected transfer did not report error")
    end
    "reset_during_traffic": begin
     if(reset_delay<1) `uvm_fatal("SOC_RESET_BOUNDS","positive reset delay required")
     b.start_traffic(); b.wait_cycles(reset_delay); b.traffic_pending(pending);
     if(!pending) begin b.stop_traffic(); `uvm_fatal("SOC_NO_TRAFFIC","no pending traffic") end
     b.reset(); b.check_reset(aborted,checks); b.stop_traffic();
     if(!aborted) `uvm_fatal("SOC_RESET_ABORT","missing observed reset abort")
    end
    default: `uvm_fatal("SOC_SCENARIO_NAME","unknown scenario")
   endcase
   if(checks<1) `uvm_fatal("SOC_NO_CHECKS","scenario has no checks")
  endtask
 endclass
endpackage
