// Reusable bench infrastructure. Protocol agents publish rvw_transaction objects.
package rvw_base_pkg;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 `uvm_analysis_imp_decl(_expected)
 `uvm_analysis_imp_decl(_actual)
 class rvw_transaction extends uvm_sequence_item;
  rand bit write;
  rand bit [63:0] address, data;
  `uvm_object_utils_begin(rvw_transaction)
   `uvm_field_int(write,UVM_ALL_ON)
   `uvm_field_int(address,UVM_ALL_ON)
   `uvm_field_int(data,UVM_ALL_ON)
  `uvm_object_utils_end
  function new(string name="rvw_transaction"); super.new(name); endfunction
 endclass
 class rvw_scoreboard extends uvm_scoreboard;
  `uvm_component_utils(rvw_scoreboard)
  uvm_analysis_imp_expected #(rvw_transaction,rvw_scoreboard) expected;
  uvm_analysis_imp_actual #(rvw_transaction,rvw_scoreboard) actual;
  rvw_transaction pending[$];
  int unsigned checks;
  function new(string name,uvm_component parent);
   super.new(name,parent); expected=new("expected",this); actual=new("actual",this);
  endfunction
  function void write_expected(rvw_transaction t);
   rvw_transaction copy;
   $cast(copy,t.clone()); pending.push_back(copy);
  endfunction
  function void write_actual(rvw_transaction t);
   rvw_transaction e;
   if(pending.size()==0) begin `uvm_error("UNEXPECTED","no expected transaction") return; end
   e=pending.pop_front();
   if(!e.compare(t)) `uvm_error("MISMATCH","transaction differs")
   checks++;
  endfunction
  function void check_phase(uvm_phase phase);
   super.check_phase(phase);
   if(pending.size()!=0) `uvm_error("MISSING","expected transactions remain")
   if(checks==0) `uvm_error("NO_CHECKS","scoreboard received no comparisons")
  endfunction
 endclass
 class rvw_virtual_sequencer extends uvm_sequencer;
  `uvm_component_utils(rvw_virtual_sequencer)
  // A project environment sets these to the appropriate agent sequencers.
  uvm_sequencer_base instruction, memory, interrupt, debug_agent;
  uvm_reg_block registers;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
 endclass
 class rvw_coverage extends uvm_subscriber #(rvw_transaction);
  `uvm_component_utils(rvw_coverage)
  bit [7:0] hit_bins;
  int unsigned samples;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void write(rvw_transaction t);
   hit_bins[{t.write,t.address[3:2]}]=1; samples++;
  endfunction
  function void report_phase(uvm_phase phase);
   `uvm_info("COVERAGE",$sformatf("address/op bins=%0d/8 samples=%0d",$countones(hit_bins),samples),UVM_LOW)
  endfunction
 endclass
 class rvw_env extends uvm_env;
  `uvm_component_utils(rvw_env)
  rvw_scoreboard scoreboard;
  rvw_virtual_sequencer vseqr;
  rvw_coverage coverage;
  uvm_reg_block registers;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void build_phase(uvm_phase phase);
   super.build_phase(phase);
   scoreboard=rvw_scoreboard::type_id::create("scoreboard",this);
   vseqr=rvw_virtual_sequencer::type_id::create("vseqr",this);
   coverage=rvw_coverage::type_id::create("coverage",this);
   if(uvm_config_db#(uvm_reg_block)::get(this,"","registers",registers)) vseqr.registers=registers;
  endfunction
  // The caller supplies its bus adapter. Backdoor paths belong to project data.
  function void bind_frontdoor(uvm_sequencer_base seqr,uvm_reg_adapter adapter);
   registers.default_map.set_sequencer(seqr,adapter);
   registers.default_map.set_auto_predict(1);
  endfunction
 endclass
 class rvw_sequence extends uvm_sequence;
  `uvm_object_utils(rvw_sequence)
  function new(string name="rvw_sequence"); super.new(name); endfunction
  task pre_body(); if(get_starting_phase()!=null) get_starting_phase().raise_objection(this); endtask
  task post_body(); if(get_starting_phase()!=null) get_starting_phase().drop_objection(this); endtask
 endclass
 class rvw_test extends uvm_test;
  `uvm_component_utils(rvw_test)
  rvw_env env;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void build_phase(uvm_phase phase);
   super.build_phase(phase); env=rvw_env::type_id::create("env",this);
  endfunction
  function void report_phase(uvm_phase phase);
   uvm_report_server server=uvm_report_server::get_server();
   if(server.get_severity_count(UVM_ERROR)==0 && server.get_severity_count(UVM_FATAL)==0 && env.scoreboard.checks>0)
    $display("RVW_UVM_DONE %s checks=%0d",get_type_name(),env.scoreboard.checks);
  endfunction
 endclass
endpackage
