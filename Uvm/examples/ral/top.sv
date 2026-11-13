package ral_test_pkg;
 import uvm_pkg::*;
 import rvw_ral::*;
 import rvw_ral_pkg::*;
 `include "uvm_macros.svh"
 class register_driver extends uvm_driver #(register_transfer);
  `uvm_component_utils(register_driver)
  bit [31:0] memory[4];
  int checks;
  uvm_analysis_port #(register_transfer) observed;
  function new(string name,uvm_component parent); super.new(name,parent); observed=new("observed",this); endfunction
  task run_phase(uvm_phase phase);
   forever begin
    seq_item_port.get_next_item(req);
    if(req.address>=16 || req.address%4) req.status=UVM_NOT_OK;
    else begin
     if(req.write) memory[req.address/4]=req.data[31:0];
     else req.data=memory[req.address/4];
     req.status=UVM_IS_OK; checks++; observed.write(req);
    end
    seq_item_port.item_done();
   end
  endtask
 endclass
 class fixture_backdoor extends uvm_reg_backdoor;
  `uvm_object_utils(fixture_backdoor)
  register_driver driver;
  int index;
  function new(string name="fixture_backdoor"); super.new(name); endfunction
  virtual task write(uvm_reg_item rw);
   driver.memory[index]=rw.value[0][31:0]; rw.status=UVM_IS_OK;
  endtask
  virtual task read(uvm_reg_item rw); read_func(rw); endtask
  virtual function void read_func(uvm_reg_item rw);
   rw.value[0]=driver.memory[index]; rw.status=UVM_IS_OK;
  endfunction
 endclass
 class ral_smoke extends uvm_test;
  `uvm_component_utils(ral_smoke)
  register_block model;
  uvm_sequencer #(register_transfer) seqr;
  register_driver driver;
  register_adapter adapter;
  register_predictor predictor;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void build_phase(uvm_phase phase);
   model=new("model"); model.build();
   seqr=new("seqr",this); driver=new("driver",this); adapter=new(); predictor=new("predictor",this);
  endfunction
  function void connect_phase(uvm_phase phase);
   driver.seq_item_port.connect(seqr.seq_item_export);
   model.default_map.set_sequencer(seqr,adapter);
   model.default_map.set_auto_predict(0);
   predictor.map=model.default_map; predictor.adapter=adapter;
   driver.observed.connect(predictor.bus_in);
  endfunction
  task run_phase(uvm_phase phase);
   register_sequences seq=new();
   uvm_reg regs[$];
   phase.raise_objection(this);
   seq.model=model; seq.reset_check(); seq.bit_bash();
   // Each register needs its own physical offset for this fixture backdoor.
   model.get_registers(regs);
   foreach(regs[i]) begin
    fixture_backdoor bd=new(); bd.driver=driver; bd.index=regs[i].get_offset()/4;
    regs[i].set_backdoor(bd);
   end
   seq.access_check();
   phase.drop_objection(this);
  endtask
  function void report_phase(uvm_phase phase);
   uvm_report_server server=uvm_report_server::get_server();
   if(server.get_severity_count(UVM_ERROR)==0 && server.get_severity_count(UVM_FATAL)==0 && driver.checks>0)
    $display("RVW_UVM_DONE ral_smoke checks=%0d",driver.checks);
  endfunction
 endclass
endpackage
module top;
 import uvm_pkg::*; import ral_test_pkg::*;
 initial run_test("ral_smoke");
 initial begin #100000; $fatal(1,"watchdog"); end
endmodule
