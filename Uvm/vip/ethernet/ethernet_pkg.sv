package ethernet_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class packet extends uvm_sequence_item;
    `uvm_object_utils(packet)
    byte unsigned data[];bit dropped,error,interrupt;
    function new(string name="packet");super.new(name);endfunction
  endclass
  virtual class native_model extends uvm_object;
    function new(string name="native_model");super.new(name);endfunction
    pure virtual task exchange(packet request,output packet observed);
  endclass
  class adapter extends uvm_component;
    `uvm_component_utils(adapter)
    string model_name,model_version;native_model backend;int count;
    covergroup traffic with function sample(int length,bit dropped,error);
      lengths:coverpoint length;drops:coverpoint dropped;errors:coverpoint error;
    endgroup
    function new(string name,uvm_component parent);super.new(name,parent);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      void'(uvm_config_db#(string)::get(this,"","model_name",model_name));
      void'(uvm_config_db#(string)::get(this,"","model_version",model_version));
      if(model_name=="" || model_version=="") `uvm_fatal("ETH_MODEL_CONTRACT","declare model and version")
      if(!uvm_config_db#(native_model)::get(this,"","backend",backend) || backend==null) `uvm_fatal("ETH_MODEL_MISSING","missing backend")
    endfunction
    task transfer(packet request,bit expected_drop=0,bit expected_error=0);
      packet actual;
      if(request.data.size()<1 || request.data.size()>9216) `uvm_fatal("ETH_PACKET_LENGTH","packet outside profile")
      backend.exchange(request,actual);
      if(actual==null) `uvm_fatal("ETH_MODEL_NO_RESULT","missing model result")
      if(actual.dropped!=expected_drop || actual.error!=expected_error) `uvm_fatal("ETH_RX_OUTCOME","wrong outcome")
      if(!expected_drop && !expected_error)begin
        if(actual.data.size()!=request.data.size() || !actual.interrupt) `uvm_fatal("ETH_PACKET_DATA","length or interrupt mismatch")
        foreach(actual.data[i])if(actual.data[i]!=request.data[i]) `uvm_fatal("ETH_PACKET_DATA","payload mismatch")
      end
      traffic.sample(request.data.size(),actual.dropped,actual.error);count++;
    endtask
    function void check_phase(uvm_phase phase);if(count==0) `uvm_fatal("ETH_MISSING_PACKET","no packets") endfunction
  endclass
endpackage
