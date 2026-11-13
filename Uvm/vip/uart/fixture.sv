// Seeded behavioural serial echo DUT. No UART register/FIFO implementation.
module uart_echo(uart_if b);
  import uart_vip::*;
  monitor m; subordinate model;
  initial begin
    uvm_pkg::uvm_config_db#(virtual uart_if)::set(null,"fixture*","bus",b);
    m=new("fixture_monitor",null); model=new("fixture_model",null);
    m.build_phase(null); m.observe_tx=1; model.build_phase(null);
    model.buggy=$test$plusargs("buggy"); m.ap.connect(model.fifo.analysis_export);
    fork m.run_phase(null); model.run_phase(null); join
  end
endmodule
