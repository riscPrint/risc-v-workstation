package axis_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  `uvm_analysis_imp_decl(_input)
  `uvm_analysis_imp_decl(_output)
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [31:0] data;
    rand bit [3:0] keep, strobe, user;
    rand bit [1:0] id, destination;
    bit last=1;
    constraint legal { (strobe & ~keep)==0; }
    function new(string name="item"); super.new(name); endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed"); super.new(name); endfunction
    task body();
      item t;
      for(int keep=0;keep<16;keep++) for(int positions=0;positions<2;positions++) begin
        t=new(); start_item(t); t.keep=4'(keep); t.strobe=positions ? 0 : 4'(keep);
        t.data=$urandom; t.user=4'(keep); t.id=2'(keep); t.destination=2'(keep/4);
        finish_item(t);
      end
      for(int i=0;i<4;i++) begin
        t=new(); start_item(t); t.keep=15; t.strobe=15; t.data=32'(i+1);
        t.id=2'(i%2); t.last=i>=2; finish_item(t);
      end
    endtask
  endclass
  class random_sequence extends uvm_sequence#(item);
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body();
      item t; bit [1:0] id,dest; int beats;
      repeat(32) begin
        id=2'($urandom); dest=2'($urandom); beats=$urandom_range(1,8);
        for(int i=0;i<beats;i++) begin
          t=new(); start_item(t);
          if(t.randomize()!=1) `uvm_fatal("AXIS_RANDOM","randomization failed")
          t.id=id; t.destination=dest; t.last=i+1==beats; finish_item(t);
        end
      end
    endtask
  endclass
  class error_sequence extends uvm_sequence#(item);
    `uvm_object_utils(error_sequence)
    function new(string name="error_sequence"); super.new(name); endfunction
    task body();
      item t;
      repeat(4) begin
        t=new(); start_item(t); t.keep=15; t.strobe=15; t.data=42; finish_item(t);
      end
    endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual axis_if b;
    bit inject_data;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual axis_if)::get(this,"","bus",b)) `uvm_fatal("AXIS_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t; int waited;
      forever begin
        seq_item_port.get_next_item(t); wait(b.reset_n);
        @(negedge b.clk);
        b.tvalid=1; b.tdata=t.data; b.tkeep=t.keep; b.tstrb=t.strobe;
        b.tid=t.id; b.tdest=t.destination; b.tlast=t.last; b.tuser=t.user;
        waited=0;
        forever begin
          @(posedge b.clk);
          if(!b.reset_n || b.tready) break;
          waited++;
          if(waited>=1000) `uvm_fatal("AXIS_TIMEOUT","source policy limit")
          if(inject_data) begin @(negedge b.clk); b.tdata^=1; end
        end
        @(negedge b.clk); b.tvalid=0;
        seq_item_port.item_done();
      end
    endtask
  endclass
  class subordinate extends uvm_component;
    `uvm_component_utils(subordinate)
    virtual axis_if b;
    bit hold;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual axis_if)::get(this,"","bus",b)) `uvm_fatal("AXIS_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      forever begin @(negedge b.clk); b.tready=!hold && ($urandom_range(0,3)!=0); end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual axis_if b;
    uvm_analysis_port#(item) ap;
    bit active_packet[16];
    int count, packets, stalls;
    covergroup traffic with function sample(bit [3:0] keep,strobe,user, bit [1:0] id,dest, bit last);
      keeps: coverpoint keep;
      strobes: coverpoint strobe;
      users: coverpoint user;
      ids: coverpoint id;
      destinations: coverpoint dest;
      ends: coverpoint last;
      routing: cross ids,destinations;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); traffic=new(); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual axis_if)::get(this,"","bus",b)) `uvm_fatal("AXIS_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin
        @(posedge b.clk);
        if(!b.reset_n) foreach(active_packet[i]) active_packet[i]=0;
        else if(b.tvalid) begin
          if(!b.tready) stalls++;
          else begin
            t=new(); t.data=b.tdata; t.keep=b.tkeep; t.strobe=b.tstrb;
            t.user=b.tuser; t.id=b.tid; t.destination=b.tdest; t.last=b.tlast;
            active_packet[{t.id,t.destination}]=!t.last;
            count++; if(t.last) packets++;
            traffic.sample(t.keep,t.strobe,t.user,t.id,t.destination,t.last);
            ap.write(t);
          end
        end
      end
    endtask
    function void check_phase(uvm_phase phase);
      foreach(active_packet[i]) if(active_packet[i]) `uvm_fatal("AXIS_UNTERMINATED_PACKET","missing TLAST")
    endfunction
  endclass
  class scoreboard extends uvm_component;
    `uvm_component_utils(scoreboard)
    uvm_analysis_imp_input#(item,scoreboard) input_port;
    uvm_analysis_imp_output#(item,scoreboard) output_port;
    int unsigned tokens[16][$];
    int count;
    function new(string name,uvm_component parent);
      super.new(name,parent); input_port=new("input_port",this); output_port=new("output_port",this);
    endfunction
    function void reset_model(); foreach(tokens[i]) tokens[i].delete(); endfunction
    function void token(bit [3:0] stream, int unsigned value, bit expected);
      int unsigned got;
      if(expected) tokens[stream].push_back(value);
      else begin
        if(tokens[stream].size()==0) `uvm_fatal("AXIS_PACKET_DATA_ORDER","unexpected output token")
        got=tokens[stream].pop_front();
        if(got!=value) `uvm_fatal("AXIS_PACKET_DATA_ORDER","output token mismatch")
      end
    endfunction
    function void sample(item t, bit expected);
      int unsigned value;
      for(int lane=0;lane<4;lane++) if(t.keep[lane]) begin
        value=(t.strobe[lane] ? int'(t.data[8*lane+:8]) : 256) | (int'(t.user[lane])<<9);
        token({t.id,t.destination},value,expected);
      end
      if(t.last) begin token({t.id,t.destination},1024,expected); if(!expected) count++; end
    endfunction
    function void write_input(item t); sample(t,1); endfunction
    function void write_output(item t); sample(t,0); endfunction
    function void check_phase(uvm_phase phase);
      if(count==0) `uvm_fatal("AXIS_MISSING_PACKET","no completed output packets")
      foreach(tokens[i]) if(tokens[i].size()!=0) `uvm_fatal("AXIS_MISSING_PACKET","undrained input tokens")
    endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d; subordinate sub; monitor m; uvm_sequencer#(item) s;
    bit subordinate_role=0;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      void'(uvm_config_db#(bit)::get(this,"","subordinate_role",subordinate_role));
      m=new("m",this);
      if(is_active==UVM_ACTIVE) begin
        if(subordinate_role) sub=new("sub",this);
        else begin d=new("d",this); s=new("s",this); end
      end
    endfunction
    function void connect_phase(uvm_phase phase); if(d!=null) d.seq_item_port.connect(s.seq_item_export); endfunction
  endclass
endpackage
