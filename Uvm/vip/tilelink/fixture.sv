module tilelink_ram(tilelink_if b);
  import tilelink_vip::*;
  subordinate model;
  initial begin
    uvm_pkg::uvm_config_db#(virtual tilelink_if)::set(null,"fixture_model","bus",b);
    model=new("fixture_model",null); model.build_phase(null);
    model.buggy=$test$plusargs("buggy"); model.run_phase(null);
  end
endmodule
