module tilelink_ram(tilelink_if b);
  import tilelink_vip::*;
  subordinate model;
  initial begin
    uvm_pkg::uvm_config_db#(virtual tilelink_if)::set(null,"fixture_model","bus",b);
    model=new("fixture_model",null);
    model.buggy=$test$plusargs("buggy");
  end
endmodule
