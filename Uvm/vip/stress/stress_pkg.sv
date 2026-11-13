package stress_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    bit response,write,error;bit [3:0] source,txn;bit [1:0] qos;bit [31:0] address;bit [63:0] data;int cycle;
    function new(string name="item");super.new(name);endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed");super.new(name);endfunction
    task body();item t;
      for(int i=0;i<16;i++)begin
        t=new();start_item(t);t.txn=4'(i);t.source=4'(i%4);t.address=32'(i);t.qos=2'(i%4);finish_item(t);
        t=new();start_item(t);t.response=1;t.txn=4'(i);t.source=4'(i%4);t.address=32'(i);finish_item(t);
      end
    endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual stress_if b;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual stress_if)::get(this,"","bus",b)) `uvm_fatal("STRESS_CONFIG","missing bridge")
    endfunction
    task run_phase(uvm_phase phase);item t;int cycles;
      forever begin seq_item_port.get_next_item(t);wait(b.reset_n);@(negedge b.clk);
        b.valid=1;b.response=t.response;b.txn=t.txn;b.source=t.source;b.address=t.address;b.write=t.write;b.error=t.error;b.qos=t.qos;b.data=t.data;cycles=0;
        do begin @(posedge b.clk);cycles++;if(cycles>100) `uvm_fatal("STRESS_TIMEOUT","bridge timeout") end while(!b.ready);
        @(negedge b.clk);b.valid=0;seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    int observed_transactions;
    virtual stress_if b;uvm_analysis_port#(item) ap;int cycle;
    covergroup traffic with function sample(int source,qos);sources:coverpoint source;classes:coverpoint qos;endgroup
    function new(string name,uvm_component parent);super.new(name,parent);ap=new("ap",this);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual stress_if)::get(this,"","bus",b)) `uvm_fatal("STRESS_CONFIG","missing bridge")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin @(posedge b.clk);cycle++;if(b.reset_n && b.valid && b.ready)begin
        t=new();t.response=b.response;t.txn=b.txn;t.source=b.source;t.address=b.address;t.write=b.write;t.error=b.error;t.qos=b.qos;t.data=b.observed_data;t.cycle=cycle;
        if(t.response) observed_transactions++; ap.write(t);traffic.sample(int'(t.source),int'(t.qos));
      end end
    endtask
    function void check_phase(uvm_phase phase);
      string idle_reason;
      if(observed_transactions==0 && (!uvm_config_db#(string)::get(this,"","idle_reason",idle_reason) || idle_reason.len()==0))
        `uvm_fatal("NO_CHECKS","no_checks: zero observed transactions")
    endfunction
  endclass
  class scoreboard extends uvm_subscriber#(item);
    `uvm_component_utils(scoreboard)
    bit active[4][16],expected_error[4][16];int started[4][16],used[4];
    bit [63:0] expected[4][16],memory[64];int count,max_wait=32;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void write(item t);int n,tx;bit error;
      n=int'(t.source);tx=int'(t.txn);
      if(n>=4) `uvm_fatal("STRESS_PROFILE","source outside profile")
      if(!t.response)begin
        if(active[n][tx]) `uvm_fatal("STRESS_DUPLICATE_TXN","duplicate request")
        if(used[n]>=4) `uvm_fatal("STRESS_NO_CREDIT","no credit")
        error=t.address>=64;active[n][tx]=1;used[n]++;started[n][tx]=t.cycle;expected_error[n][tx]=error;
        expected[n][tx]=error || t.write ? 0 : memory[t.address];
        if(t.write && !error)memory[t.address]=t.data;
      end else begin
        if(!active[n][tx]) `uvm_fatal("STRESS_UNKNOWN_RESPONSE","unknown response")
        if(t.cycle-started[n][tx]>max_wait) `uvm_fatal("STRESS_STARVATION","wait exceeds declared bound")
        if(t.data!=expected[n][tx] || t.error!=expected_error[n][tx]) `uvm_fatal("STRESS_RESPONSE_DATA","response mismatch")
        active[n][tx]=0;used[n]--;count++;
      end
    endfunction
    function void check_phase(uvm_phase phase);
      foreach(active[n,tx])if(active[n][tx]) `uvm_fatal("STRESS_MISSING_RESPONSE","pending request")
      if(count==0) `uvm_fatal("STRESS_NO_RESPONSES","no responses")
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
