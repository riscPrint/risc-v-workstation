// Seeded behavioural serial echo DUT. No UART register/FIFO implementation.
module uart_echo(uart_if b);
  import uart_vip::*;
  monitor m; subordinate model;
  initial begin
    uvm_pkg::uvm_config_db#(virtual uart_if)::set(null,"fixture*","bus",b);
    uvm_pkg::uvm_config_db#(bit)::set(null,"fixture_monitor","observe_tx",1);
    m=new("fixture_monitor",null); model=new("fixture_model",null);
    model.buggy=$test$plusargs("buggy"); m.ap.connect(model.fifo.analysis_export);
  end
endmodule
