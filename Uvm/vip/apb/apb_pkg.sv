package apb_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [31:0] address, data;
    rand bit write;
    rand bit [3:0] strobe;
    rand bit [2:0] protection;
    int waits;
    bit [31:0] response;
    bit error, aborted;
    constraint legal { address inside {0,4,8,12,16}; if(!write) strobe==0; }
    function new(string name="item"); super.new(name); endfunction
  endclass

  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed"); super.new(name); endfunction
    task body();
      item t;
      for(int i=0;i<16;i++) begin
        t=new(); start_item(t);
        t.address=(i/4)*4; t.write=(i%2)==0;
        t.data=32'h12345678+i; t.strobe=t.write ? (i%4==0 ? 15 : 5) : 0;
        finish_item(t);
      end
      for(int i=0;i<2;i++) begin
        t=new(); start_item(t); t.address=16; t.write=1'(i); t.strobe=i ? 15 : 0;
        finish_item(t);
      end
    endtask
  endclass
  class random_sequence extends uvm_sequence#(item);
    `uvm_object_utils(random_sequence)
    int count=32;
    function new(string name="random_sequence"); super.new(name); endfunction
    task body();
      item t;
      repeat(count) begin
        t=new(); start_item(t);
        if(!t.randomize()) `uvm_fatal("APB_RANDOM","randomization failed")
        finish_item(t);
      end
    endtask
  endclass
  class error_sequence extends uvm_sequence#(item);
    `uvm_object_utils(error_sequence)
    function new(string name="error_sequence"); super.new(name); endfunction
    task body();
      item t=new(); start_item(t); t.address=0; t.write=1; t.strobe=15; t.data=1;
      // Driver option inject_address changes PADDR after SETUP.
      finish_item(t);
    endtask
  endclass

  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual apb_if b;
    bit inject_address=0;
    int timeout_cycles=1000;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual apb_if)::get(this,"","bus",b))
        `uvm_fatal("APB_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin
        seq_item_port.get_next_item(t);
        wait(b.reset_n);
        @(negedge b.clk);
        b.psel=1; b.penable=0; b.paddr=t.address; b.pwrite=t.write;
        b.pwdata=t.data; b.pstrb=t.strobe; b.pprot=t.protection;
        @(negedge b.clk); b.penable=1;
        if(inject_address) b.paddr^=4;
        t.waits=0;
        forever begin
          @(posedge b.clk);
          if(!b.reset_n) begin t.aborted=1; break; end
          if(b.pready) begin t.response=b.prdata; t.error=b.pslverr; break; end
          t.waits++;
          if(t.waits>=timeout_cycles) `uvm_fatal("APB_TIMEOUT","driver policy limit")
        end
        @(negedge b.clk); b.psel=0; b.penable=0;
        seq_item_port.item_done();
      end
    endtask
  endclass

  // Reactive subordinate role. Use instead of a DUT subordinate, never with it.
  class subordinate extends uvm_component;
    `uvm_component_utils(subordinate)
    virtual apb_if b;
    bit [31:0] memory[4];
    int waits;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual apb_if)::get(this,"","bus",b))
        `uvm_fatal("APB_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      forever begin
        @(negedge b.clk); #1;
        if(!b.reset_n) begin
          foreach(memory[i]) memory[i]=0;
          waits=0; b.pready=0; b.pslverr=0; b.prdata=0;
        end else begin
          if(b.psel && !b.penable) waits=$urandom_range(0,3);
          b.pready=waits==0;
          b.pslverr=b.paddr>=16 || b.paddr[1:0]!=0;
          b.prdata=b.pslverr ? 0 : memory[b.paddr>>2];
          @(posedge b.clk);
          if(b.reset_n && b.psel && b.penable) begin
            if(waits>0) waits--;
            else if(b.pwrite && !b.pslverr)
              for(int i=0;i<4;i++) if(b.pstrb[i]) memory[b.paddr>>2][8*i+:8]=b.pwdata[8*i+:8];
          end
        end
      end
    endtask
  endclass

  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual apb_if b;
    uvm_analysis_port#(item) ap;
    item pending;
    int wait_count;
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual apb_if)::get(this,"","bus",b))
        `uvm_fatal("APB_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      forever begin
        @(posedge b.clk);
        if(!b.reset_n) begin
          if(pending!=null) begin pending.aborted=1; ap.write(pending); end
          pending=null; wait_count=0;
        end else if(b.psel) begin
          if(!b.penable) begin
            pending=new(); pending.address=b.paddr; pending.write=b.pwrite;
            pending.data=b.pwdata; pending.strobe=b.pstrb; pending.protection=b.pprot;
            wait_count=0;
          end else if(b.pready) begin
            if(pending==null) `uvm_fatal("APB_SETUP","monitor missing setup")
            pending.response=b.prdata; pending.error=b.pslverr; pending.waits=wait_count;
            ap.write(pending); pending=null;
          end else wait_count++;
        end
      end
    endtask
  endclass

  class scoreboard extends uvm_subscriber#(item);
    `uvm_component_utils(scoreboard)
    bit [31:0] model[4];
    int count, errors, waited, reads, writes, aborts;
    covergroup traffic with function sample(bit wr, bit err, int wait_cycles, bit [3:0] mask);
      direction: coverpoint wr;
      response: coverpoint err;
      delay_cycles: coverpoint wait_cycles { bins zero={0}; bins wait_state={[1:3]}; }
      strobes: coverpoint mask;
      operation_response: cross direction,response;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); traffic=new(); endfunction
    function void reset_model(); foreach(model[i]) model[i]=0; endfunction
    function void write(item t);
      bit expected_error;
      if(t.aborted) begin aborts++; return; end
      expected_error=t.address>=16 || t.address[1:0]!=0;
      if(t.error!=expected_error) `uvm_fatal("APB_RESPONSE","error response mismatch")
      if(!t.error) begin
        if(t.write) begin
          for(int i=0;i<4;i++) if(t.strobe[i]) model[t.address>>2][8*i+:8]=t.data[8*i+:8];
        end else if(t.response!==model[t.address>>2]) `uvm_fatal("APB_DATA","read data mismatch")
      end
      count++; if(t.error) errors++; if(t.waits) waited++;
      if(t.write) writes++; else reads++;
      traffic.sample(t.write,t.error,t.waits,t.strobe);
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
    function void connect_phase(uvm_phase phase);
      if(d!=null) d.seq_item_port.connect(s.seq_item_export);
    endfunction
  endclass
endpackage
