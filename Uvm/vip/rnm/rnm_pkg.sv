package rnm_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class contract extends uvm_object;
    `uvm_object_utils(contract)
    string backend_name,backend_version,unit_name;
    bit supports_real;
    function new(string name="contract");super.new(name);endfunction
    function void validate();
      if(backend_name=="" || backend_version=="" || unit_name=="" || !supports_real)
        `uvm_fatal("RNM_BACKEND_CONTRACT","declare real-number backend, version and units")
    endfunction
  endclass
  class boundary_stub extends uvm_component;
    `uvm_component_utils(boundary_stub)
    virtual rnm_if b;contract declaration;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(contract)::get(this,"","contract",declaration)) `uvm_fatal("RNM_BACKEND_CONTRACT","missing contract")
      declaration.validate();
      if(!uvm_config_db#(virtual rnm_if)::get(this,"","bus",b)) `uvm_fatal("RNM_BOUNDARY_BUS","missing boundary")
    endfunction
    task run_phase(uvm_phase phase);
      forever begin @(posedge b.clk);
        if(b.valid && !b.known) `uvm_fatal("RNM_UNKNOWN_VALUE","real sample is not known")
      end
    endtask
    function void report_phase(uvm_phase phase);
      `uvm_info("RNM_STUB","inconclusive: model_not_bound",UVM_LOW)
    endfunction
  endclass
endpackage
