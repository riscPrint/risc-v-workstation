package pcie_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    bit write;bit [7:0] tag;bit [63:0] address;byte unsigned data[];int length;
    bit success;
    function new(string name="item");super.new(name);endfunction
  endclass
  virtual class native_model extends uvm_object;
    function new(string name="native_model");super.new(name);endfunction
    pure virtual task exchange(item request,output item completion);
  endclass
  class adapter extends uvm_component;
    `uvm_component_utils(adapter)
    string model_name,model_version;native_model backend;
    bit memory_enable;bit [63:0] base=64'h1000,window_size=256;
    byte unsigned memory[longint unsigned];
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      void'(uvm_config_db#(string)::get(this,"","model_name",model_name));
      void'(uvm_config_db#(string)::get(this,"","model_version",model_version));
      if(model_name=="" || model_version=="") `uvm_fatal("PCIE_MODEL_CONTRACT","declare native model and version")
      if(!uvm_config_db#(native_model)::get(this,"","backend",backend) || backend==null) `uvm_fatal("PCIE_MODEL_MISSING","missing backend")
    endfunction
    task transfer(item request,output item completion);
      byte unsigned expected;
      if(!memory_enable) `uvm_fatal("PCIE_MEMORY_DISABLED","memory access disabled")
      if(request.length<1 || request.length>4096 || request.address<base || request.address+64'(request.length)>base+window_size)
        `uvm_fatal("PCIE_ADDRESS_WINDOW","request outside window")
      if(request.write && request.data.size()!=request.length) `uvm_fatal("PCIE_WRITE_LENGTH","payload length")
      backend.exchange(request,completion);
      if(request.write)begin
        foreach(request.data[i])memory[request.address+64'(i)]=request.data[i];
      end else begin
        if(completion==null) `uvm_fatal("PCIE_MISSING_COMPLETION","no completion")
        if(!completion.success || completion.tag!=request.tag || completion.data.size()!=request.length)
          `uvm_fatal("PCIE_COMPLETION_DATA","completion metadata mismatch")
        foreach(completion.data[i])begin
          expected=memory.exists(request.address+64'(i)) ? memory[request.address+64'(i)] : 0;
          if(completion.data[i]!=expected) `uvm_fatal("PCIE_COMPLETION_DATA","read data mismatch")
        end
      end
    endtask
  endclass
endpackage
