package i2c_test;
  import uvm_pkg::*; import i2c_vip::*;
  `include "uvm_macros.svh"
  class test_env extends uvm_test;
    `uvm_component_utils(test_env)
    agent source; scoreboard sc;
    function new(string name="test_env",uvm_component parent=null); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase); source=new("source",this); sc=new("sc",this); endfunction
    function void connect_phase(uvm_phase phase); source.m.ap.connect(sc.analysis_export); endfunction
    function void end_of_elaboration_phase(uvm_phase phase);
      set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
    endfunction
    task run_phase(uvm_phase phase);
      item e; directed ds=new();
      phase.raise_objection(this);
      for(int i=0;i<4;i++) begin e=new(); e.data=8'(i*85); e.ack=1; sc.expected.push_back(e); end
      ds.start(source.s); repeat(20) @(posedge source.d.b.clk);
      sc.check_phase(phase); source.m.check_phase(phase);
      $display("RVW_I2C_DONE bytes=%0d",sc.count); phase.drop_objection(this);
    endtask
  endclass
endpackage
module top;
  import uvm_pkg::*;
  bit clk=0; always #5 clk=~clk;
  i2c_if bus(clk); i2c_target dut(bus); i2c_checker checker_i(bus);
  initial begin #20; bus.reset_n=1; end
  initial begin uvm_config_db#(virtual i2c_if)::set(null,"uvm_test_top.source*","bus",bus); run_test("test_env"); end
  initial begin #1000000; $fatal(1,"I2C_WATCHDOG"); end
endmodule
