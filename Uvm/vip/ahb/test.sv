package ahb_test;
  import uvm_pkg::*; import ahb_vip::*;
  `include "uvm_macros.svh"
  class test_env extends uvm_test;
    `uvm_component_utils(test_env)
    agent a; scoreboard sc;
    function new(string name="test_env",uvm_component parent=null); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase); a=new("a",this); sc=new("sc",this); endfunction
    function void connect_phase(uvm_phase phase); a.m.ap.connect(sc.analysis_export); endfunction
    function void end_of_elaboration_phase(uvm_phase phase);
      set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
    endfunction
    task run_phase(uvm_phase phase);
      directed ds=new(); random_sequence rs=new(); error_sequence es=new();
      phase.raise_objection(this);
      if($test$plusargs("bad_manager")) begin a.d.inject_address=1; es.start(a.s); end
      else begin ds.start(a.s); rs.start(a.s); end
      #20;
      if(sc.count<374 || sc.errors<2 || sc.waited==0) `uvm_fatal("AHB_CHECK","missing traffic")
      $display("RVW_AHB_DONE count=%0d errors=%0d waits=%0d",sc.count,sc.errors,sc.waited);
      phase.drop_objection(this);
    endtask
  endclass
endpackage
module top;
  import uvm_pkg::*;
  bit clk=0;
  always #5 clk=~clk;
  ahb_if bus(clk);
  ahb_ram dut(bus);
  ahb_checker checker_inst(bus);
  initial begin #20; bus.reset_n=1; end
  initial begin
    uvm_config_db#(virtual ahb_if)::set(null,"*","bus",bus);
    run_test("test_env");
  end
  initial begin #100000; $fatal(1,"AHB_WATCHDOG"); end
endmodule
