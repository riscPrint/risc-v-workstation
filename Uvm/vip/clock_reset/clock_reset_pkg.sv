package clock_reset_vip;
  timeunit 1ns;timeprecision 1ps;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand int cycles;
    bit clock,reset_n;time timestamp;
    constraint duration {cycles inside {[8:32]};}
    function new(string name="item");super.new(name);cycles=16;endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed");super.new(name);endfunction
    task body();item t=new();start_item(t);t.cycles=16;finish_item(t);endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence");super.new(name);endfunction
    task body();item t=new();start_item(t);void'(t.randomize());finish_item(t);endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual clock_reset_if b;int reset_cycles=2;time half_period=5;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual clock_reset_if)::get(this,"","bus",b)) `uvm_fatal("CLOCK_RESET_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin seq_item_port.get_next_item(t);b.clock=0;b.reset_n=0;
        for(int i=0;i<t.cycles;i++)begin
          #(half_period);b.clock=1;#(half_period);b.clock=0;
          if(i+1==reset_cycles)b.reset_n=1;
        end
        seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual clock_reset_if b;uvm_analysis_port#(item) ap;
    covergroup traffic with function sample(bit clock,reset_n);
      clocks:coverpoint clock;resets:coverpoint reset_n;
    endgroup
    function new(string name,uvm_component parent);super.new(name,parent);ap=new("ap",this);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual clock_reset_if)::get(this,"","bus",b)) `uvm_fatal("CLOCK_RESET_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin @(b.observed_clock or b.observed_reset_n);#1ps;t=new();
        t.clock=b.observed_clock;t.reset_n=b.observed_reset_n;t.timestamp=$time;
        ap.write(t);traffic.sample(t.clock,t.reset_n);
      end
    endtask
  endclass
  class scoreboard extends uvm_subscriber#(item);
    `uvm_component_utils(scoreboard)
    bit old_clock,old_reset;time last_edge;int reset_edges,count,releases;time half_period=5;int reset_cycles=2;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void write(item t);
      if(t.clock!=old_clock)begin
        if(count>0 && t.timestamp-last_edge!=half_period) `uvm_fatal("CLOCK_HALF_PERIOD","wrong period")
        last_edge=t.timestamp;count++;
        if(t.clock && !t.reset_n)reset_edges++;
      end
      if(old_reset && !t.reset_n)reset_edges=0;
      if(!old_reset && t.reset_n)begin
        if(t.clock || !old_clock) `uvm_fatal("RESET_RELEASE_EDGE","release on wrong edge")
        if(reset_edges<reset_cycles) `uvm_fatal("RESET_TOO_SHORT","short reset")
        releases++;
      end
      old_clock=t.clock;old_reset=t.reset_n;
    endfunction
    function void check_phase(uvm_phase phase);
      if(count==0 || releases==0 || !old_reset) `uvm_fatal("CLOCK_RESET_NO_SEQUENCE","incomplete sequence")
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
