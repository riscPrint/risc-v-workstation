// A pin-level fixture. This is not a CPU interrupt controller or debug module.
interface control_if(input bit clk);
 bit [31:0] irq, observed_irq;
 bit halt_req, resume_req, halted, ack;
endinterface
module control_fixture(control_if p);
 always @(posedge p.clk) begin
   p.observed_irq <= p.irq ^ ($test$plusargs("pins_corrupt") ? 8 : 0);
   p.ack <= p.halt_req || p.resume_req;
   if(p.halt_req) p.halted <= 1;
   if(p.resume_req) p.halted <= 0;
 end
endmodule
package control_vip;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 class pin_item extends uvm_sequence_item;
   `uvm_object_utils(pin_item)
   bit [31:0] irq;
   bit halt_req,resume_req;
   function new(string name="pin_item"); super.new(name); endfunction
 endclass
 class pin_sequence extends uvm_sequence#(pin_item);
   `uvm_object_utils(pin_sequence)
   function new(string name="pin_sequence"); super.new(name); endfunction
   task body();
     pin_item t;
     for(int i=0;i<6;i++) begin
       t=new(); start_item(t);
       t.irq=i<4 ? (32'(1) << (i==0 ? 3 : i==1 ? 7 : i==2 ? 9 : 11)) : 0;
       t.halt_req=i==4; t.resume_req=i==5;
       finish_item(t);
     end
   endtask
 endclass
 class pin_driver extends uvm_driver#(pin_item);
   `uvm_component_utils(pin_driver)
   virtual control_if p;
   function new(string name,uvm_component parent); super.new(name,parent); endfunction
   task run_phase(uvm_phase phase);
     pin_item t;
     forever begin
       seq_item_port.get_next_item(t);
       @(negedge p.clk); p.irq=t.irq; p.halt_req=t.halt_req; p.resume_req=t.resume_req;
       @(posedge p.clk); #2;
       @(negedge p.clk); p.irq=0; p.halt_req=0; p.resume_req=0;
       @(posedge p.clk); #2; seq_item_port.item_done();
     end
   endtask
 endclass
 class pin_monitor extends uvm_component;
   `uvm_component_utils(pin_monitor)
   virtual control_if p;
   int seen;
   bit expected_halt;
   function new(string name,uvm_component parent); super.new(name,parent); endfunction
   task run_phase(uvm_phase phase);
     forever begin
       @(posedge p.clk);
       if(p.halt_req && p.resume_req) `uvm_fatal("PINS","conflicting debug requests")
       if(p.halt_req) expected_halt=1;
       if(p.resume_req) expected_halt=0;
       if(p.irq || p.halt_req || p.resume_req) seen++;
       #1;
       if(p.observed_irq!=p.irq || p.halted!=expected_halt || p.ack!=(p.halt_req || p.resume_req))
         `uvm_fatal("PINS","interrupt/debug pin mismatch")
     end
   endtask
   function void check_phase(uvm_phase phase);
     if(seen!=6 || expected_halt) `uvm_fatal("PINS","missing transitions")
     $display("RVW_UVM_PASS interrupt_debug_pins");
   endfunction
 endclass
 class pin_agent extends uvm_agent;
   `uvm_component_utils(pin_agent)
   pin_driver d; pin_monitor m; uvm_sequencer#(pin_item) s;
   virtual control_if p;
   function new(string name,uvm_component parent); super.new(name,parent); endfunction
   function void build_phase(uvm_phase phase);
     if(!uvm_config_db#(virtual control_if)::get(this,"","pins",p)) `uvm_fatal("PINS","missing interface")
     d=new("d",this); m=new("m",this); s=new("s",this); d.p=p; m.p=p;
   endfunction
   function void connect_phase(uvm_phase phase); d.seq_item_port.connect(s.seq_item_export); endfunction
   task run_phase(uvm_phase phase);
     pin_sequence sequence_;
     phase.raise_objection(this); sequence_=new(); sequence_.start(s); phase.drop_objection(this);
   endtask
 endclass
endpackage
