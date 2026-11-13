package sram_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit enable,write;
    rand bit [31:0] address,data;
    rand bit [3:0] mask;
    bit reset_n=1,valid;bit [31:0] response;
    constraint profile {address<16;}
    function new(string name="item");super.new(name);endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed");super.new(name);endfunction
    task body();item t;
      for(int i=0;i<4;i++)begin t=new();start_item(t);t.enable=1;t.address=0;t.write=i%2==0;t.data='h12345678;t.mask=15;finish_item(t);end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence");super.new(name);endfunction
    task body();item t;repeat(32)begin t=new();start_item(t);void'(t.randomize());finish_item(t);end endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual sram_if b;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual sram_if)::get(this,"","bus",b)) `uvm_fatal("MEM_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin seq_item_port.get_next_item(t);wait(b.reset_n);@(negedge b.clk);
        b.enable=t.enable;b.write=t.write;b.address=t.address;b.data=t.data;b.mask=t.mask;
        @(posedge b.clk);seq_item_port.item_done();@(negedge b.clk);b.enable=0;
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    int observed_transactions;
    virtual sram_if b;uvm_analysis_port#(item) ap;
    covergroup traffic with function sample(bit enable,write,valid,bit [3:0] mask);
      enables:coverpoint enable;writes:coverpoint write;responses:coverpoint valid;masks:coverpoint mask;
    endgroup
    function new(string name,uvm_component parent);super.new(name,parent);ap=new("ap",this);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual sram_if)::get(this,"","bus",b)) `uvm_fatal("MEM_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin @(posedge b.clk);t=new();t.reset_n=b.reset_n;t.enable=b.enable;t.write=b.write;
        t.address=b.address;t.data=b.data;t.mask=b.mask;t.valid=b.valid;t.response=b.response;
        observed_transactions++; ap.write(t);traffic.sample(t.enable,t.write,t.valid,t.mask);
      end
    endtask
    function void check_phase(uvm_phase phase);
      string idle_reason;
      if(observed_transactions==0 && (!uvm_config_db#(string)::get(this,"","idle_reason",idle_reason) || idle_reason.len()==0))
        `uvm_fatal("NO_CHECKS","no_checks: zero observed transactions")
    endfunction
  endclass
  class scoreboard extends uvm_subscriber#(item);
    `uvm_component_utils(scoreboard)
    bit [31:0] memory[16],pending;bit pending_valid,readonly;int count;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void write(item t);
      if(!t.reset_n)begin foreach(memory[i])memory[i]=0;pending_valid=0;end
      else begin
        if(t.valid!=pending_valid || t.valid && t.response!=pending) `uvm_fatal("MEM_READ_DATA_OR_LATENCY","read mismatch")
        if(t.valid)count++;pending_valid=0;
        if(t.enable)begin
          if(t.address>=16) `uvm_fatal("MEM_ADDRESS","out of range")
          if(t.write)begin
            if(readonly) `uvm_fatal("MEM_ROM_WRITE","write to ROM")
            for(int i=0;i<4;i++)if(t.mask[i])memory[t.address][8*i+:8]=t.data[8*i+:8];
          end else begin pending=memory[t.address];pending_valid=1;end
        end
      end
    endfunction
    function void check_phase(uvm_phase phase);
      if(pending_valid || count==0) `uvm_fatal("MEM_MISSING_READ","missing read")
    endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d;monitor m;uvm_sequencer#(item) s;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);m=new("m",this);if(is_active==UVM_ACTIVE)begin d=new("d",this);s=new("s",this);end endfunction
    function void connect_phase(uvm_phase phase);if(d!=null)d.seq_item_port.connect(s.seq_item_export);endfunction
  endclass
endpackage
