package dram_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class model_contract extends uvm_object;
    `uvm_object_utils(model_contract)
    string model_name,model_version,mode;
    int clock_ps;
    function new(string name="model_contract");super.new(name);endfunction
    function void validate();
      if(model_name=="" || model_version=="" || !(mode inside {"functional","timing"}) || clock_ps<=0)
        `uvm_fatal("DRAM_MODEL_CONTRACT","declare model, version, mode and clock")
    endfunction
  endclass
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    int cycle,command,bank,row,column;
    bit [63:0] data;
    function new(string name="item");super.new(name);endfunction
  endclass
  virtual class native_model extends uvm_object;
    function new(string name="native_model");super.new(name);endfunction
    // A project implements this task using its chosen model and license.
    pure virtual task execute(item command,output bit read_valid,output bit [63:0] data,output int response_cycle);
  endclass
  class adapter extends uvm_component;
    `uvm_component_utils(adapter)
    model_contract contract;
    native_model backend;
    virtual dram_if b;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(model_contract)::get(this,"","contract",contract)) `uvm_fatal("DRAM_MODEL_CONTRACT","missing contract")
      contract.validate();
      if(!uvm_config_db#(native_model)::get(this,"","backend",backend) || backend==null) `uvm_fatal("DRAM_MODEL_MISSING","missing native model")
      if(!uvm_config_db#(virtual dram_if)::get(this,"","bus",b)) `uvm_fatal("DRAM_MODEL_BUS","missing bridge")
    endfunction
    task run_phase(uvm_phase phase);
      item c;bit valid;bit [63:0] data;int response_cycle,cycle;
      forever begin @(posedge b.clk);cycle++;
        if(b.reset_n && b.valid && b.ready)begin
          c=new();c.cycle=cycle;c.command=int'(b.command);c.bank=b.bank;c.row=b.row;c.column=b.column;c.data=b.write_data;
          backend.execute(c,valid,data,response_cycle);
          // The project schedules backend responses on its declared timebase.
          // No implicit pass or unimplemented timing is reported here.
        end
      end
    endtask
  endclass
endpackage
