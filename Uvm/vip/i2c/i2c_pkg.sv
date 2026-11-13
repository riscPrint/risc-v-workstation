package i2c_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [7:0] data;
    bit ack;
    function new(string name="item"); super.new(name); endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed"); super.new(name); endfunction
    task body(); item t;
      for(int i=0;i<4;i++) begin t=new(); start_item(t); t.data=8'(i*85); finish_item(t); end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body(); item t;
      repeat(32) begin t=new(); start_item(t); t.data=8'($urandom); finish_item(t); end
    endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual i2c_if b;
    int stretch_limit=100;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual i2c_if)::get(this,"","bus",b)) `uvm_fatal("I2C_CONFIG","missing bus")
    endfunction
    task drive(bit scl_low,sda_low);
      @(negedge b.clk); b.manager_scl_low=scl_low; b.manager_sda_low=sda_low;
      repeat(3) @(negedge b.clk);
      if(!b.reset_n) `uvm_fatal("I2C_RESET","reset during transfer")
    endtask
    task high(bit sda_low,arbitrate=0);
      int n=0;
      drive(0,sda_low);
      while(!b.scl && n<stretch_limit) begin drive(0,sda_low); n++; end
      if(!b.scl) begin drive(0,0); `uvm_fatal("I2C_STRETCH_TIMEOUT","clock held low") end
      if(arbitrate && !sda_low && !b.sda) begin drive(0,0); `uvm_fatal("I2C_ARBITRATION_LOST","release bus") end
    endtask
    task run_phase(uvm_phase phase);
      item t;
      forever begin
        seq_item_port.get_next_item(t); wait(b.reset_n);
        high(0); if(!b.sda) `uvm_fatal("I2C_BUS_BUSY","bus is busy")
        drive(0,1); drive(1,1);
        for(int i=7;i>=0;i--) begin drive(1,!t.data[i]); high(!t.data[i],1); drive(1,!t.data[i]); end
        drive(1,0); high(0); t.ack=!b.sda; drive(1,0);
        drive(1,1); high(1); drive(0,0); seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual i2c_if b; uvm_analysis_port#(item) ap;
    bit old_scl=1,old_sda=1,active; int bits,count; bit [7:0] value;
    covergroup traffic with function sample(bit ack,bit repeated_start);
      acks:coverpoint ack; starts:coverpoint repeated_start;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); traffic=new(); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual i2c_if)::get(this,"","bus",b)) `uvm_fatal("I2C_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin @(posedge b.clk);
        if(!b.reset_n) begin active=0; bits=0; value=0; old_scl=1; old_sda=1; end
        else begin
          if($isunknown({b.scl,b.sda})) `uvm_fatal("I2C_UNKNOWN_LINE","unknown line")
          if(old_scl && b.scl && old_sda!=b.sda) begin
            if(bits>1) `uvm_fatal("I2C_PARTIAL_BYTE","boundary within byte")
            bits=0; value=0;
            if(!b.sda) begin traffic.sample(0,active); active=1; end
            else begin if(!active) `uvm_fatal("I2C_INVALID_STOP","stop without start") active=0; end
          end else if(!old_scl && b.scl && active) begin
            if(bits<8) begin value={value[6:0],b.sda}; bits++; end
            else begin t=new(); t.data=value; t.ack=!b.sda; ap.write(t); count++; traffic.sample(t.ack,0); bits=0; value=0; end
          end
          old_scl=b.scl; old_sda=b.sda;
        end
      end
    endtask
    function void check_phase(uvm_phase phase);
      if(active || bits!=0) `uvm_fatal("I2C_UNFINISHED_TRANSFER","missing stop")
    endfunction
  endclass
  class scoreboard extends uvm_subscriber#(item);
    `uvm_component_utils(scoreboard)
    item expected[$]; int count;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void write(item t);
      item e;
      if(expected.size()==0) `uvm_fatal("I2C_BYTE_STREAM","unexpected byte")
      e=expected.pop_front();
      if({e.data,e.ack}!={t.data,t.ack}) `uvm_fatal("I2C_BYTE_STREAM","byte mismatch")
      count++;
    endfunction
    function void check_phase(uvm_phase phase);
      if(expected.size()>0 || count==0) `uvm_fatal("I2C_MISSING_BYTE","missing byte")
    endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d; monitor m; uvm_sequencer#(item) s;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      m=new("m",this);
      if(is_active==UVM_ACTIVE) begin d=new("d",this); s=new("s",this); end
    endfunction
    function void connect_phase(uvm_phase phase); if(d!=null) d.seq_item_port.connect(s.seq_item_export); endfunction
  endclass
endpackage
