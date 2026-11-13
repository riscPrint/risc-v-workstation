package jtag_test;
  import uvm_pkg::*; import jtag_vip::*;
  `include "uvm_macros.svh"
  class test_env extends uvm_test;
    `uvm_component_utils(test_env)
    agent source; scoreboard sc;
    function new(string name="test_env",uvm_component parent=null); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase); source=new("source",this); sc=new("sc",this); endfunction
    function void connect_phase(uvm_phase phase); source.d.expected.connect(sc.input_port);source.m.ap.connect(sc.output_port); endfunction
    function void end_of_elaboration_phase(uvm_phase phase);
      set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
    endfunction
    task run_phase(uvm_phase phase);
      directed ds=new(); random_sequence rs=new(); phase.raise_objection(this);
      ds.start(source.s); rs.start(source.s); repeat(8) @(negedge source.d.b.clk);
      sc.check_phase(phase); $display("RVW_JTAG_DONE samples=%0d",sc.count); phase.drop_objection(this);
    endtask
  endclass
endpackage
module top;
  import uvm_pkg::*;
  bit clk=0; always #5 clk=~clk;
  jtag_if bus(clk); jtag_fixture dut(bus); 
  
  initial begin uvm_config_db#(virtual jtag_if)::set(null,"uvm_test_top.source*","bus",bus); run_test("test_env"); end
  initial begin #1000000; $fatal(1,"JTAG_WATCHDOG"); end
endmodule
