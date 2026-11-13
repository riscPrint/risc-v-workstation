package axis_test;
  import uvm_pkg::*; import axis_vip::*;
  `include "uvm_macros.svh"
  class test_env extends uvm_test;
    `uvm_component_utils(test_env)
    agent source,sink; scoreboard sc;
    function new(string name="test_env",uvm_component parent=null); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      uvm_config_db#(bit)::set(this,"sink","subordinate_role",1);
      source=new("source",this); sink=new("sink",this); sc=new("sc",this);
    endfunction
    function void connect_phase(uvm_phase phase);
      source.m.ap.connect(sc.input_port); sink.m.ap.connect(sc.output_port);
    endfunction
    function void end_of_elaboration_phase(uvm_phase phase);
      set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
    endfunction
    task run_phase(uvm_phase phase);
      directed ds=new(); random_sequence rs=new(); error_sequence es=new();
      phase.raise_objection(this);
      if($test$plusargs("bad_manager")) begin
        source.d.inject_data=1; sink.sub.hold=1; es.start(source.s);
      end else begin ds.start(source.s); rs.start(source.s); end
      repeat(100) @(posedge source.d.b.clk);
      if(sc.count!=66 || source.m.count!=sink.m.count || sink.m.stalls==0)
        `uvm_fatal("AXIS_CHECK","missing packets or stall coverage")
      $display("RVW_AXIS_DONE packets=%0d",sc.count);
      phase.drop_objection(this);
    endtask
  endclass
endpackage
module top;
  import uvm_pkg::*;
  bit clk=0;
  always #5 clk=~clk;
  axis_if s(clk),m(clk);
  assign m.reset_n=s.reset_n;
  axis_fifo dut(s,m);
  axis_checker source_checker(s),sink_checker(m);
  initial begin #20; s.reset_n=1; end
  initial begin
    uvm_config_db#(virtual axis_if)::set(null,"uvm_test_top.source*","bus",s);
    uvm_config_db#(virtual axis_if)::set(null,"uvm_test_top.sink*","bus",m);
    run_test("test_env");
  end
  initial begin #100000; $fatal(1,"AXIS_WATCHDOG"); end
endmodule
