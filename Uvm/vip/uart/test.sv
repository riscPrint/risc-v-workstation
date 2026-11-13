package uart_test;
  import uvm_pkg::*; import uart_vip::*;
  `include "uvm_macros.svh"
  class test_env extends uvm_test;
    `uvm_component_utils(test_env)
    agent source; monitor tx_monitor; scoreboard sc;
    function new(string name="test_env",uvm_component parent=null); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      uvm_config_db#(bit)::set(this,"tx_monitor","observe_tx",1);
      source=new("source",this); tx_monitor=new("tx_monitor",this); sc=new("sc",this);
    endfunction
    function void connect_phase(uvm_phase phase);
      tx_monitor.ap.connect(sc.input_port); source.m.ap.connect(sc.output_port);
    endfunction
    function void end_of_elaboration_phase(uvm_phase phase);
      uvm_root::get().set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
    endfunction
    task run_phase(uvm_phase phase);
      directed ds=new(); random_sequence rs=new(); error_sequence es=new();
      phase.raise_objection(this); ds.data_bits=source.d.b.data_bits; rs.data_bits=ds.data_bits;
      ds.start(source.s); rs.start(source.s);
      if($test$plusargs("errors")) es.start(source.s);
      repeat(5000) @(posedge source.d.b.clk);
      sc.check_phase(phase); $display("RVW_UART_DONE frames=%0d",sc.count); phase.drop_objection(this);
    endtask
  endclass
endpackage
module top;
  import uvm_pkg::*;
  bit clk=0; always #5 clk=~clk;
  uart_if bus(clk);
  uart_echo dut(bus); uart_checker checker_i(bus);
  initial begin #20; bus.reset_n=1; end
  initial begin
    uvm_config_db#(virtual uart_if)::set(null,"uvm_test_top.*","bus",bus); run_test("test_env");
  end
  initial begin #1000000; $fatal(1,"UART_WATCHDOG"); end
endmodule
