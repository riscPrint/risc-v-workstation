package interrupt_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  `uvm_analysis_imp_decl(_expected)
  `uvm_analysis_imp_decl(_observed)
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [7:0] levels;rand int cycles;
    constraint duration {cycles inside {[1:8]};}
    function new(string name="item");super.new(name);cycles=1;endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed");super.new(name);endfunction
    task body();item t;
      for(int i=0;i<4;i++)begin t=new();start_item(t);t.levels=i[0]?'1:0;t.cycles=2;finish_item(t);end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence");super.new(name);endfunction
    task body();item t;repeat(32)begin t=new();start_item(t);void'(t.randomize());finish_item(t);end endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual interrupt_if b;uvm_analysis_port#(item) expected;
    function new(string name,uvm_component parent);super.new(name,parent);expected=new("expected",this);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual interrupt_if)::get(this,"","bus",b)) `uvm_fatal("IRQ_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin seq_item_port.get_next_item(t);wait(b.reset_n);@(negedge b.clk);b.levels=t.levels;expected.write(t);
        repeat(t.cycles)@(posedge b.clk);seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual interrupt_if b;uvm_analysis_port#(item) ap;bit [7:0] previous;int lengths[8];int min_pulse=1;
    covergroup traffic with function sample(bit [7:0] levels,edges);
      values:coverpoint levels;transitions:coverpoint edges;
    endgroup
    function new(string name,uvm_component parent);super.new(name,parent);ap=new("ap",this);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual interrupt_if)::get(this,"","bus",b)) `uvm_fatal("IRQ_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin @(posedge b.clk);
        if(!b.reset_n)begin previous=0;foreach(lengths[i])lengths[i]=0;end
        else begin
          if($isunknown(b.observed)) `uvm_fatal("IRQ_UNKNOWN_OR_WIDE","unknown line")
          for(int i=0;i<8;i++)begin
            if(b.observed[i])lengths[i]++;
            else if(previous[i])begin if(lengths[i]<min_pulse) `uvm_fatal("IRQ_SHORT_PULSE","short pulse") lengths[i]=0;end
          end
          t=new();t.levels=b.observed;ap.write(t);traffic.sample(t.levels,t.levels^previous);previous=t.levels;
        end
      end
    endtask
  endclass
  class scoreboard extends uvm_component;
    `uvm_component_utils(scoreboard)
    uvm_analysis_imp_expected#(item,scoreboard) input_port;
    uvm_analysis_imp_observed#(item,scoreboard) output_port;
    bit [7:0] expected[$];int count;
    function new(string name,uvm_component parent);
      super.new(name,parent);input_port=new("input_port",this);output_port=new("output_port",this);
    endfunction
    function void write_expected(item t);repeat(t.cycles)expected.push_back(t.levels);endfunction
    function void write_observed(item t);bit [7:0] value;
      // Only scheduled windows have expected values. Gaps remain passive.
      if(expected.size()>0)begin value=expected.pop_front();if(value!=t.levels) `uvm_fatal("IRQ_LEVEL_OR_TIMING","line mismatch") count++;end
    endfunction
    function void check_phase(uvm_phase phase);
      if(count==0 || expected.size()>0) `uvm_fatal("IRQ_MISSING_SAMPLES","missing samples")
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
