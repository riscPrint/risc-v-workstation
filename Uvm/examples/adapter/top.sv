module top;
 import uvm_pkg::*;
 import rvw_base_pkg::*;
 `include "uvm_macros.svh"
 // Replace this fixture with a DUT and connect its monitor to the scoreboard.
 class adapter_smoke extends rvw_test;
  `uvm_component_utils(adapter_smoke)
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  task run_phase(uvm_phase phase);
   rvw_transaction t=new("t");
   phase.raise_objection(this);
   for(int i=0;i<8;i++) begin
    t.write=bit'(i>>2); t.address=(i%4)*4; t.data=i;
    env.scoreboard.write_expected(t);
    #1;
    env.scoreboard.write_actual(t); env.coverage.write(t);
   end
   phase.drop_objection(this);
  endtask
 endclass
 initial run_test();
 // The C++ harness writes native coverage at the end of simulation.
endmodule
