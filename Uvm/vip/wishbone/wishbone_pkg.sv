package wishbone_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [31:0] address,data;
    rand bit write;
    rand bit [3:0] select;
    bit [31:0] response; bit error;
    constraint profile {address<64;address[1:0]==0;}
    function new(string name="item"); super.new(name); endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed"); super.new(name); endfunction
    task body(); item t;
      for(int i=0;i<4;i++) begin t=new(); start_item(t); t.address=0;t.write=i%2==0;t.data='h12345678;t.select=15;finish_item(t);end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence");super.new(name);endfunction
    task body();item t;repeat(32)begin t=new();start_item(t);void'(t.randomize());finish_item(t);end endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual wishbone_if b;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual wishbone_if)::get(this,"","bus",b)) `uvm_fatal("WB_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;int cycles;
      forever begin seq_item_port.get_next_item(t);wait(b.reset_n);@(negedge b.clk);
        b.cyc=1;b.stb=1;b.adr=t.address;b.we=t.write;b.dat_w=t.data;b.sel=t.select;cycles=0;
        do begin @(posedge b.clk);cycles++;
          if(!b.reset_n) `uvm_fatal("WB_RESET_ABORT","reset in cycle")
          if(cycles>100) `uvm_fatal("WB_TIMEOUT","test policy timeout")
        end while(!b.ack && !b.err);
        t.response=b.dat_r;t.error=b.err;
        @(negedge b.clk);b.cyc=0;b.stb=0;seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    int observed_transactions;
    virtual wishbone_if b;uvm_analysis_port#(item) ap;
    covergroup traffic with function sample(bit write,error,bit [3:0] select);
      writes:coverpoint write;errors:coverpoint error;selects:coverpoint select;
    endgroup
    function new(string name,uvm_component parent);super.new(name,parent);ap=new("ap",this);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual wishbone_if)::get(this,"","bus",b)) `uvm_fatal("WB_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin @(posedge b.clk);
        if(b.reset_n && b.cyc && b.stb && (b.ack || b.err)) begin
          t=new();t.address=b.adr;t.data=b.dat_w;t.write=b.we;t.select=b.sel;t.response=b.dat_r;t.error=b.err;
          observed_transactions++; ap.write(t);traffic.sample(t.write,t.error,t.select);
        end
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
    bit [31:0] memory[16];int count;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void write(item t);
      bit error;error=t.address>=64 || t.address[1:0]!=0;
      if(t.error!=error) `uvm_fatal("WB_ERROR_RESPONSE","wrong termination")
      if(!error) begin
        if(t.write) begin for(int i=0;i<4;i++)if(t.select[i])memory[t.address>>2][8*i+:8]=t.data[8*i+:8];end
        else if(t.response!=memory[t.address>>2]) `uvm_fatal("WB_READ_DATA","wrong read")
      end
      count++;
    endfunction
    function void check_phase(uvm_phase phase);if(count==0) `uvm_fatal("WB_NO_TRANSFERS","no transfers") endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d;monitor m;uvm_sequencer#(item) s;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);m=new("m",this);if(is_active==UVM_ACTIVE)begin d=new("d",this);s=new("s",this);end endfunction
    function void connect_phase(uvm_phase phase);if(d!=null)d.seq_item_port.connect(s.seq_item_export);endfunction
  endclass
endpackage
