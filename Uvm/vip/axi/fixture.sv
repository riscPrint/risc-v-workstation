// RAM fixture uses the same subordinate engine on the passive DUT side.
// +buggy changes each read by one bit. Seed with +verilator+seed+N.
module axi_ram(axi_if b);
  import axi_vip::*;
  subordinate model;
  initial begin
    uvm_pkg::uvm_config_db#(virtual axi_if)::set(null,"fixture_model","bus",b);
    model=new("fixture_model",null);
    model.build_phase(null); model.buggy=$test$plusargs("buggy");
    model.run_phase(null);
  end
endmodule
