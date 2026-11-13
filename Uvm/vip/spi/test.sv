package spi_test;
  import uvm_pkg::*; import spi_vip::*;
  `include "uvm_macros.svh"
  class test_env extends uvm_test;
    `uvm_component_utils(test_env)
    agent source; scoreboard sc;
    function new(string name="test_env",uvm_component parent=null); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase); source=new("source",this); sc=new("sc",this); endfunction
    function void connect_phase(uvm_phase phase);
      source.d.expected.connect(sc.input_port); source.m.ap.connect(sc.output_port);
    endfunction
    task run_phase(uvm_phase phase);
      directed ds=new(); random_sequence rs=new(); error_sequence es=new();
      phase.raise_objection(this); ds.bits=source.d.b.bits; rs.bits=ds.bits;
      if($test$plusargs("bad_manager")) es.start(source.s);
      else begin ds.start(source.s); rs.start(source.s); end
      repeat(20) @(posedge source.d.b.clk);
      sc.check_phase(phase); source.m.check_phase(phase);
      $display("RVW_SPI_DONE words=%0d",sc.count); phase.drop_objection(this);
    endtask
  endclass
endpackage
module top;
  import uvm_pkg::*;
  bit clk=0; always #5 clk=~clk;
  spi_if bus(clk); spi_loopback dut(bus); spi_checker checker_i(bus);
  initial begin
    bus.polarity=$test$plusargs("cpol"); bus.phase=$test$plusargs("cpha"); bus.sclk=bus.polarity;
    #20; bus.reset_n=1;
  end
  initial begin
    uvm_config_db#(virtual spi_if)::set(null,"uvm_test_top.source*","bus",bus); run_test("test_env");
  end
  initial begin #1000000; $fatal(1,"SPI_WATCHDOG"); end
endmodule
