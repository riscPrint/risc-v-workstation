package gpio_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [7:0] external_value,direction,output_value;
    bit [7:0] sampled,irq;
    bit reset_n=1;
    function new(string name="item"); super.new(name); endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed"); super.new(name); endfunction
    task body(); item t;
      for(int i=0;i<8;i++) begin t=new(); start_item(t);
        t.reset_n=i!=0; t.external_value=i[0] ? '1 : 0;
        t.direction=i[1] ? '1 : 0; t.output_value=i[2] ? '1 : 0; finish_item(t);
      end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body(); item t;
      repeat(32) begin t=new(); start_item(t); void'(t.randomize()); finish_item(t); end
    endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual gpio_if b;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual gpio_if)::get(this,"","bus",b)) `uvm_fatal("GPIO_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin seq_item_port.get_next_item(t); @(negedge b.clk);
        b.reset_n=t.reset_n; b.external_value=t.external_value; b.direction=t.direction; b.output_value=t.output_value;
        @(posedge b.clk); seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual gpio_if b; uvm_analysis_port#(item) ap;
    covergroup traffic with function sample(bit [7:0] direction,irq,bit reset_n);
      directions:coverpoint direction; interrupts:coverpoint irq; resets:coverpoint reset_n;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); traffic=new(); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual gpio_if)::get(this,"","bus",b)) `uvm_fatal("GPIO_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin @(posedge b.clk); t=new(); t.reset_n=b.reset_n;
        t.external_value=b.external_value; t.direction=b.direction; t.output_value=b.output_value;
        if($isunknown({b.sampled,b.irq})) `uvm_fatal("GPIO_UNKNOWN_PIN","unknown input")
        t.sampled=b.sampled; t.irq=b.irq; ap.write(t); traffic.sample(t.direction,t.irq,t.reset_n);
      end
    endtask
  endclass
  class scoreboard extends uvm_subscriber#(item);
    `uvm_component_utils(scoreboard)
    bit [7:0] pipe_values[$]; bit [7:0] previous;
    bit [7:0] rising_mask=1,falling_mask=2,high_mask=4,low_mask=8;
    int sync_cycles=2,count;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void write(item t);
      bit [7:0] value,irq;
      if(!t.reset_n) begin pipe_values.delete(); previous=0; value=0; irq=0; end
      else begin
        while(pipe_values.size()<sync_cycles) pipe_values.push_back(0);
        pipe_values.push_back((t.output_value&t.direction)|(t.external_value&~t.direction));
        value=pipe_values.pop_front();
        irq=(value&~previous&rising_mask)|(~value&previous&falling_mask)|(value&high_mask)|(~value&low_mask);
      end
      if({t.sampled,t.irq}!={value,irq}) `uvm_fatal("GPIO_STATE_OR_IRQ","reference mismatch")
      previous=value; count++;
    endfunction
    function void check_phase(uvm_phase phase);
      if(count==0) `uvm_fatal("GPIO_NO_SAMPLES","no samples")
    endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d; monitor m; uvm_sequencer#(item) s;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      m=new("m",this); if(is_active==UVM_ACTIVE) begin d=new("d",this); s=new("s",this); end
    endfunction
    function void connect_phase(uvm_phase phase); if(d!=null) d.seq_item_port.connect(s.seq_item_export); endfunction
  endclass
endpackage
