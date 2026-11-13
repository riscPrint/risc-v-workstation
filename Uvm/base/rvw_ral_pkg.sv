// Normalized register bus items. Project agents translate them to their bus.
package rvw_ral_pkg;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 class register_transfer extends uvm_sequence_item;
  `uvm_object_utils(register_transfer)
  bit write;
  uvm_reg_addr_t address;
  uvm_reg_data_t data;
  uvm_status_e status=UVM_NOT_OK;
  function new(string name="register_transfer"); super.new(name); endfunction
 endclass
 class register_adapter extends uvm_reg_adapter;
  `uvm_object_utils(register_adapter)
  function new(string name="register_adapter"); super.new(name); endfunction
  virtual function uvm_sequence_item reg2bus(const ref uvm_reg_bus_op rw);
   register_transfer t=register_transfer::type_id::create("transfer");
   t.write=(rw.kind==UVM_WRITE); t.address=rw.addr; t.data=rw.data;
   return t;
  endfunction
  virtual function void bus2reg(uvm_sequence_item bus_item, ref uvm_reg_bus_op rw);
   register_transfer t;
   if(!$cast(t,bus_item)) begin
    rw.status=UVM_NOT_OK; `uvm_error("RAL_ITEM","expected register_transfer") return;
   end
   rw.kind=t.write ? UVM_WRITE : UVM_READ;
   rw.addr=t.address; rw.data=t.data; rw.status=t.status;
  endfunction
 endclass
 class register_predictor extends uvm_reg_predictor #(register_transfer);
  `uvm_component_utils(register_predictor)
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
 endclass
 // The caller resets the DUT before reset_check. Access needs a real backdoor.
 class register_sequences extends uvm_sequence;
  `uvm_object_utils(register_sequences)
  uvm_reg_block model;
  function new(string name="register_sequences"); super.new(name); endfunction
  task reset_check();
   uvm_reg_hw_reset_seq seq=new("reset_check");
   if(model==null) `uvm_fatal("RAL_MODEL","register model required")
   seq.model=model; seq.start(null);
  endtask
  task bit_bash();
   uvm_reg_bit_bash_seq seq=new("bit_bash");
   if(model==null) `uvm_fatal("RAL_MODEL","register model required")
   seq.model=model; seq.start(null);
  endtask
  task access_check();
   uvm_reg regs[$];
   uvm_reg_access_seq seq=new("access_check");
   if(model==null) `uvm_fatal("RAL_MODEL","register model required")
   model.get_registers(regs);
   foreach(regs[i]) if(regs[i].get_backdoor()==null && !regs[i].has_hdl_path())
    `uvm_fatal("UNSUPPORTED_RAL_BACKDOOR","access sequence requires project backdoor")
   seq.model=model; seq.start(null);
  endtask
 endclass
endpackage
