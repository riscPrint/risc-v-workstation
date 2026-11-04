package vip;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 class item extends uvm_sequence_item;
   `uvm_object_utils(item)
   rand bit [2:0] opcode;
   rand bit [31:0] address, data;
   rand bit [3:0] source;
   constraint legal { opcode inside {0,4}; address inside {0,4,8,12}; }
   bit [2:0] response;
   bit [1:0] response_param, response_size;
   bit response_denied, response_corrupt, response_sink;
   bit [3:0] response_source;
   bit [31:0] response_data;
   bit rvfi_valid;
   bit [63:0] order;
   bit [31:0] insn, mem_addr, mem_rdata, rd_wdata;
   function new(string name="item"); super.new(name); endfunction
 endclass

 class stimulus extends uvm_sequence #(item);
   `uvm_object_utils(stimulus)
   function new(string name="stimulus"); super.new(name); endfunction
   task body();
     item t;
     bit [31:0] previous_data;
     bit data_changed;
     for(int i=0;i<40;i++) begin
       t=item::type_id::create("t");
       start_item(t);
       if(!t.randomize()) `uvm_fatal("RANDOM","randomize failed")
       if (!(t.opcode inside {0,4}) || !(t.address inside {0,4,8,12}))
         `uvm_fatal("RANDOM","constraint violation")
       if(i>=8 && t.data!=previous_data) data_changed=1;
       previous_data=t.data;
       // Eight directed transactions guarantee each opcode/address bin.
       if(i<8) begin t.opcode=i<4 ? 0 : 4; t.address=(i%4)*4; end
       finish_item(t);
     end
     if(!data_changed) `uvm_fatal("RANDOM","random data did not change")
     if(t.randomize() with { opcode==3; })
       `uvm_fatal("RANDOM","unsatisfiable constraint was accepted")
   endtask
 endclass

 class driver extends uvm_driver #(item);
   `uvm_component_utils(driver)
   virtual tl_if b;
   function new(string name,uvm_component parent); super.new(name,parent); endfunction
   function void build_phase(uvm_phase phase);
     super.build_phase(phase);
     if(!uvm_config_db#(virtual tl_if)::get(this,"","bus",b))
       `uvm_fatal("CONFIG","missing bus")
   endfunction
   task run_phase(uvm_phase phase);
     item t;
     wait(!b.reset);
     forever begin
       seq_item_port.get_next_item(t);
       @(negedge b.clk);
       b.a_valid=1; b.a_opcode=t.opcode; b.a_address=t.address;
       b.a_data=t.data; b.a_source=t.source;
       do @(posedge b.clk); while(!b.a_ready);
       @(negedge b.clk); b.a_valid=0;
       do @(posedge b.clk); while(!b.d_valid);
       seq_item_port.item_done();
     end
   endtask
 endclass

 class monitor extends uvm_component;
   `uvm_component_utils(monitor)
   virtual tl_if b;
   uvm_analysis_port#(item) ap;
   function new(string name,uvm_component parent);
     super.new(name,parent); ap=new("ap",this);
   endfunction
   function void build_phase(uvm_phase phase);
     if(!uvm_config_db#(virtual tl_if)::get(this,"","bus",b))
       `uvm_fatal("CONFIG","missing bus")
   endfunction
   task run_phase(uvm_phase phase);
     item t;
     forever begin
       @(posedge b.clk);
       if(!b.reset && b.a_valid && b.a_ready) begin
         t=item::type_id::create("observed");
         if(b.a_param!=0 || b.a_size!=2 || b.a_mask!=15 || b.a_corrupt)
           `uvm_fatal("BUS","invalid fixed TL-UL request fields")
         t.opcode=b.a_opcode; t.address=b.a_address; t.data=b.a_data;
         t.source=b.a_source;
         #1;
         if(!b.d_valid) `uvm_fatal("BUS","missing response")
         t.response_param=b.d_param; t.response_size=b.d_size;
         t.response_denied=b.d_denied; t.response_corrupt=b.d_corrupt;
         t.response_sink=b.d_sink;
         t.response=b.d_opcode; t.response_data=b.d_data;
         t.response_source=b.d_source; t.rvfi_valid=b.rvfi_valid;
         t.order=b.rvfi_order; t.insn=b.rvfi_insn;
         t.mem_addr=b.rvfi_mem_addr; t.mem_rdata=b.rvfi_mem_rdata;
         t.rd_wdata=b.rvfi_rd_wdata; ap.write(t);
       end
     end
   endtask
 endclass

 class scoreboard extends uvm_subscriber#(item);
   `uvm_component_utils(scoreboard)
   bit [31:0] model[4];
   int count, loads;
   bit [7:0] seen_bins;
   covergroup traffic with function sample(bit op, bit [1:0] addr);
     cp_op: coverpoint op { bins put={0}; bins get={1}; }
     cp_addr: coverpoint addr { bins words[]={[0:3]}; }
     op_addr: cross cp_op,cp_addr;
   endgroup
   function new(string name,uvm_component parent);
     super.new(name,parent); traffic=new();
   endfunction
   function void write(item t);
     int idx;
     idx=t.address>>2;
     if(t.response_param!=0 || t.response_size!=2 || t.response_denied ||
        t.response_corrupt || t.response_sink ||
        idx>3 || t.response_source!=t.source ||
        t.response!=(t.opcode==4 ? 1 : 0))
       `uvm_fatal("TL","response mismatch")
     if(t.opcode==0) begin
       model[idx]=t.data;
       if(t.rvfi_valid) `uvm_fatal("RVFI","unexpected retirement")
     end else begin
       if(t.response_data!==model[idx] || !t.rvfi_valid ||
          t.order!=loads || t.insn!=((t.address<<20)|32'h2083) ||
          t.mem_addr!=t.address || t.mem_rdata!==model[idx] ||
          t.rd_wdata!==model[idx])
         `uvm_fatal("RVFI","load observation mismatch")
       loads++;
     end
     traffic.sample(t.opcode==4,2'(idx));
     seen_bins[(t.opcode==4 ? 4 : 0)+idx]=1;
     count++;
   endfunction
   function void check_phase(uvm_phase phase);
     if(count!=40 || loads<4 || seen_bins!=8'hff)
       `uvm_fatal("CHECK","missing transactions or coverage bins")
     if(traffic.get_inst_coverage()!=100.0)
       `uvm_fatal("COVERAGE","covergroup did not reach 100 percent")
     $display("RVW_UVM_PASS constrained_random");
     $display("RVW_UVM_PASS functional_coverage");
     $display("RVW_UVM_PASS tlul");
     $display("RVW_UVM_PASS rvfi");
   endfunction
 endclass

 class agent extends uvm_agent;
   `uvm_component_utils(agent)
   driver d; monitor m; uvm_sequencer#(item) s;
   function new(string name,uvm_component parent); super.new(name,parent); endfunction
   function void build_phase(uvm_phase phase);
     d=driver::type_id::create("d",this); m=monitor::type_id::create("m",this);
     s=new("s",this);
   endfunction
   function void connect_phase(uvm_phase phase); d.seq_item_port.connect(s.seq_item_export); endfunction
 endclass
 class test_env extends uvm_test;
   `uvm_component_utils(test_env)
   agent a; scoreboard sc;
   function new(string name="test_env",uvm_component parent=null); super.new(name,parent); endfunction
   function void build_phase(uvm_phase phase);
     a=agent::type_id::create("a",this); sc=scoreboard::type_id::create("sc",this);
   endfunction
   function void connect_phase(uvm_phase phase); a.m.ap.connect(sc.analysis_export); endfunction
   function void end_of_elaboration_phase(uvm_phase phase);
     // UVM_EXIT calls $finish, which can return zero. Make fatal exits fail.
     set_report_severity_action_hier(UVM_FATAL,UVM_DISPLAY|UVM_STOP);
   endfunction
   task run_phase(uvm_phase phase);
     stimulus s;
     phase.raise_objection(this);
     s=stimulus::type_id::create("stimulus"); s.start(a.s);
     #20;
     phase.drop_objection(this);
   endtask
   function void report_phase(uvm_phase phase);
     uvm_report_server rs;
     rs=uvm_report_server::get_server();
     if(rs.get_severity_count(UVM_ERROR)!=0 || rs.get_severity_count(UVM_FATAL)!=0)
       `uvm_fatal("REPORT","UVM error count is nonzero")
     $display("RVW_UVM_PASS phases_config_factory_tlm");
     $display("RVW_UVM_DONE");
   endfunction
 endclass
endpackage
module top;
 import uvm_pkg::*; import vip::*;
 bit clk=0;
 always #5 clk=~clk;
 tl_if bus(clk);
 tiny_ram dut(bus);
 initial begin #20; bus.reset=0; end
 initial begin
   uvm_config_db#(virtual tl_if)::set(null,"*","bus",bus);
   run_test("test_env");
 end
 initial begin #10000; $fatal(1,"watchdog"); end
endmodule
