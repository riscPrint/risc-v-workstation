package coherent_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    bit [1:0] kind,op,node;bit [3:0] txn;bit [31:0] line;bit [63:0] data;
    function new(string name="item");super.new(name);endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed");super.new(name);endfunction
    task emit(int kind,txn,node,op=0,bit [63:0] data=0);item t=new();start_item(t);
      t.kind=2'(kind);t.txn=4'(txn);t.node=2'(node);t.op=2'(op);t.data=data;finish_item(t);
    endtask
    task body();
      emit(0,0,0,1);emit(2,0,0);emit(0,1,0,2,42);emit(2,1,0,0,42);
      emit(0,2,1);emit(2,2,1,0,42);emit(0,3,0,1);emit(1,3,1);emit(2,3,0,0,42);
    endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual coherent_if b;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual coherent_if)::get(this,"","bus",b)) `uvm_fatal("COH_CONFIG","missing bridge")
    endfunction
    task run_phase(uvm_phase phase);item t;int cycles;
      forever begin seq_item_port.get_next_item(t);wait(b.reset_n);@(negedge b.clk);
        b.valid=1;b.kind=t.kind;b.txn=t.txn;b.node=t.node;b.line=t.line;b.op=t.op;b.data=t.data;cycles=0;
        do begin @(posedge b.clk);cycles++;if(cycles>100) `uvm_fatal("COH_TIMEOUT","bridge timeout") end while(!b.ready);
        @(negedge b.clk);b.valid=0;seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    int observed_transactions;
    virtual coherent_if b;uvm_analysis_port#(item) ap;
    covergroup traffic with function sample(int kind,op);kinds:coverpoint kind;ops:coverpoint op;endgroup
    function new(string name,uvm_component parent);super.new(name,parent);ap=new("ap",this);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual coherent_if)::get(this,"","bus",b)) `uvm_fatal("COH_CONFIG","missing bridge")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin @(posedge b.clk);if(b.reset_n && b.valid && b.ready)begin
        t=new();t.kind=b.kind;t.txn=b.txn;t.node=b.node;t.line=b.line;t.op=b.op;t.data=b.observed_data;
        if(t.kind==2) observed_transactions++; ap.write(t);traffic.sample(t.kind,t.op);
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
    bit active[16];int src[16],op[16],line_index[16],credits[4]='{4,4,4,4};
    bit [3:0] needed[16],holders[16];bit [63:0] memory[16],write_data[16];int owner[16];bit unique_owner[16];int count;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void write(item t);int tx,n,l;bit [63:0] expected;
      tx=int'(t.txn);n=int'(t.node);l=int'(t.line>>6);
      if(t.line[5:0]!=0 || l>=16) `uvm_fatal("COH_PROFILE","line outside reduced profile")
      if(t.kind==0)begin
        if(active[tx]) `uvm_fatal("COH_DUPLICATE_TXN","duplicate transaction")
        foreach(active[i])if(active[i] && line_index[i]==l) `uvm_fatal("COH_LINE_BUSY","line busy")
        if(credits[n]==0) `uvm_fatal("COH_NO_CREDIT","no credit")
        if(t.op==3) `uvm_fatal("COH_OPCODE","unsupported opcode")
        if(t.op==2 && (!unique_owner[l] || owner[l]!=n)) `uvm_fatal("COH_NOT_OWNER","not owner")
        active[tx]=1;src[tx]=n;op[tx]=int'(t.op);line_index[tx]=l;write_data[tx]=t.data;credits[n]--;
        needed[tx]=0;
        if(t.op==1)needed[tx]=holders[l]&~(4'b1<<n);
        else if(t.op==0 && unique_owner[l] && owner[l]!=n)needed[tx]=4'b1<<owner[l];
      end else begin
        if(!active[tx] || line_index[tx]!=l) `uvm_fatal("COH_UNKNOWN_TXN","unknown transaction or line")
        if(t.kind==1)begin
          if(!needed[tx][n]) `uvm_fatal("COH_UNEXPECTED_SNOOP_ACK","unexpected snoop acknowledgement")
          needed[tx][n]=0;if(op[tx]==1)holders[l][n]=0;
        end else if(t.kind==2)begin
          if(src[tx]!=n || needed[tx]!=0) `uvm_fatal("COH_INCOMPLETE_SNOOPS","completion before snoops")
          expected=op[tx]==2 ? write_data[tx] : memory[l];
          if(t.data!=expected) `uvm_fatal("COH_DATA","wrong coherent data")
          if(op[tx]==2)begin memory[l]=write_data[tx];holders[l][n]=0;unique_owner[l]=0;end
          else begin holders[l][n]=1;unique_owner[l]=op[tx]==1;owner[l]=n;end
          credits[n]++;active[tx]=0;count++;
        end else `uvm_fatal("COH_EVENT_KIND","unknown event")
      end
    endfunction
    function void check_phase(uvm_phase phase);
      foreach(active[i])if(active[i]) `uvm_fatal("COH_MISSING_COMPLETION","pending transaction")
      if(count==0) `uvm_fatal("COH_NO_COMPLETIONS","no completions")
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
