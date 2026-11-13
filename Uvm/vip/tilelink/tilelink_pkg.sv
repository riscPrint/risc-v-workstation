package tilelink_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    bit response;
    bit [2:0] opcode=4,param,size=2;
    bit [3:0] source,mask=15;
    bit [31:0] address,data;
    bit corrupt,denied,sink;
    function new(string name="item"); super.new(name); endfunction
    function int a_beats(); return opcode inside {0,1,2,3} ? (size>2 ? 1<<(size-2) : 1) : 1; endfunction
    function int d_opcode(); return opcode inside {2,3,4} ? 1 : opcode==5 ? 2 : 0; endfunction
    function int d_beats(); return d_opcode()==1 && size>2 ? 1<<(size-2) : 1; endfunction
    function void check_request(bit uh);
      int lanes;
      if(size>(uh ? 6 : 2) || !(opcode inside {0,1,4}) && (!uh || !(opcode inside {2,3,5})))
        `uvm_fatal("TL_PROFILE","unsupported message")
      if(address%(1<<size)!=0) `uvm_fatal("TL_ALIGNMENT","unaligned address")
      lanes=size>=2 ? 15 : ((1<<(1<<size))-1)<<(address%4);
      if((int'(mask)&~lanes)!=0 || opcode!=1 && int'(mask)!=lanes) `uvm_fatal("TL_MASK","invalid lanes")
      if(opcode==2 && (param>4 || size>2) || opcode==3 && (param>3 || size>2) ||
         opcode==5 && param>1 || opcode inside {0,1,4} && param!=0) `uvm_fatal("TL_PARAM","invalid operation")
      if(corrupt && !(opcode inside {0,1,2,3})) `uvm_fatal("TL_A_CORRUPT","no data")
    endfunction
  endclass
  class memory_model;
    bit [7:0] bytes[int unsigned];
    function void execute(item requests[$],ref item replies[$]);
      item a,t; int unsigned base; longint unsigned old,value,new_value,mask;
      longint signed signed_old,signed_value; int shift,width; bit corrupt;
      a=requests[0]; replies.delete(); corrupt=0;
      foreach(requests[i]) corrupt|=requests[i].corrupt;
      for(int i=0;i<a.d_beats();i++) begin
        t=new(); t.response=1; t.source=a.source; t.opcode=3'(a.d_opcode()); t.size=a.size;
        base=(a.address&32'hfffffffc)+32'(4*i);
        if(t.opcode==1) for(int lane=0;lane<4;lane++) t.data[8*lane+:8]=bytes.exists(base+lane) ? bytes[base+lane] : 0;
        t.denied=corrupt; t.corrupt=corrupt && t.opcode==1; replies.push_back(t);
      end
      if(corrupt) return;
      if(a.opcode inside {0,1}) foreach(requests[i]) begin
        base=(a.address&32'hfffffffc)+32'(4*i);
        for(int lane=0;lane<4;lane++) if(requests[i].mask[lane]) bytes[base+lane]=requests[i].data[8*lane+:8];
      end
      if(a.opcode inside {2,3}) begin
        width=8*(1<<a.size); shift=8*int'(a.address%4); mask=(64'b1<<width)-1;
        old=(64'(replies[0].data)>>shift)&mask; value=(64'(a.data)>>shift)&mask;
        signed_old=longint'(old<<(64-width))>>>(64-width);
        signed_value=longint'(value<<(64-width))>>>(64-width);
        if(a.opcode==2) case(a.param)
          0:new_value=signed_old<signed_value ? old : value;
          1:new_value=signed_old>signed_value ? old : value;
          2:new_value=old<value ? old : value;
          3:new_value=old>value ? old : value;
          default:new_value=old+value;
        endcase
        else case(a.param)
          0:new_value=old^value; 1:new_value=old|value; 2:new_value=old&value; default:new_value=value;
        endcase
        for(int i=0;i<(1<<a.size);i++) bytes[a.address+32'(i)]=8'(new_value>>(8*i));
      end
    endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    bit uh;
    function new(string name="directed"); super.new(name); endfunction
    task message(int op,int size=2,int param=0);
      item t; int length;
      length=op inside {0,1,2,3} && size>2 ? 1<<(size-2) : 1;
      for(int i=0;i<length;i++) begin
        t=new(); start_item(t); t.opcode=3'(op); t.param=3'(param); t.size=3'(size);
        t.address='h100; t.mask=size>=2 ? 15 : 4'((1<<(1<<size))-1); t.data=$urandom;
        finish_item(t);
      end
    endtask
    task body();
      for(int size=0;size<=(uh ? 6 : 2);size++) begin message(0,size); message(1,size); message(4,size); end
      if(uh) begin
        for(int param=0;param<5;param++) message(2,2,param);
        for(int param=0;param<4;param++) message(3,2,param);
        message(5,2,0); message(5,2,1);
      end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body(); repeat(32) begin message(0); message(4); end endtask
  endclass
  class error_sequence extends uvm_sequence#(item);
    `uvm_object_utils(error_sequence)
    function new(string name="error_sequence"); super.new(name); endfunction
    task body(); item t=new(); start_item(t); t.mask=0; finish_item(t); endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual tilelink_if b;
    int accepted,seen[16],baseline;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual tilelink_if)::get(this,"","bus",b)) `uvm_fatal("TL_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      fork collect(); drive(); join
    endtask
    task collect();
      forever begin @(posedge b.clk);
        if(!b.reset_n) foreach(seen[i]) seen[i]=0;
        else if(b.d_valid && b.d_ready) seen[b.d_source]++;
      end
    endtask
    task drive();
      item t; int waited,n;
      b.d_ready=1;
      forever begin
        seq_item_port.get_next_item(t); wait(b.reset_n); @(negedge b.clk);
        if(accepted==0) baseline=seen[t.source];
        b.a_valid=1; b.a_opcode=t.opcode; b.a_param=t.param; b.a_size=t.size;
        b.a_source=t.source; b.a_address=t.address; b.a_data=t.data; b.a_mask=t.mask; b.a_corrupt=t.corrupt;
        waited=0;
        forever begin @(posedge b.clk); if(!b.reset_n || b.a_ready) break;
          if(++waited>=1000) `uvm_fatal("TL_TIMEOUT","A policy timeout")
        end
        @(negedge b.clk); b.a_valid=0; accepted++;
        if(accepted==t.a_beats()) begin
          accepted=0; n=0; waited=0;
          while(seen[t.source]<baseline+t.d_beats()) begin @(negedge b.clk);
            if(!b.reset_n) break;

            if(++waited>=1000) `uvm_fatal("TL_TIMEOUT","D policy timeout")
          end
        end
        seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual tilelink_if b;
    uvm_analysis_port#(item) ap;
    item pending[16];
    int a_count[16],d_count[16];
    int a_active=-1,d_active=-1;
    bit uh,denied[16];
    int count;
    int completed;
    covergroup traffic with function sample(bit response,int opcode,int param,int size,int source,bit denied,bit corrupt);
      channels:coverpoint response; opcodes:coverpoint opcode; params:coverpoint param;
      sizes:coverpoint size; sources:coverpoint source; errors:coverpoint denied; corrupts:coverpoint corrupt;
      messages:cross channels,opcodes,sizes;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); traffic=new(); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual tilelink_if)::get(this,"","bus",b)) `uvm_fatal("TL_CONFIG","missing bus")
      void'(uvm_config_db#(bit)::get(this,"","uh",uh));
    endfunction
    function item capture(bit response);
      item t=new(); t.response=response;
      if(!response) begin
        t.opcode=b.a_opcode; t.param=b.a_param; t.size=b.a_size; t.source=b.a_source;
        t.address=b.a_address; t.mask=b.a_mask; t.data=b.a_data; t.corrupt=b.a_corrupt;
      end else begin
        t.opcode=b.d_opcode; t.param={1'b0,b.d_param}; t.size=b.d_size; t.source=b.d_source;
        t.data=b.d_data; t.denied=b.d_denied; t.corrupt=b.d_corrupt; t.sink=b.d_sink;
      end
      return t;
    endfunction
    function void publish(item t);
      count++; traffic.sample(t.response,int'(t.opcode),int'(t.param),int'(t.size),int'(t.source),t.denied,t.corrupt); ap.write(t);
    endfunction
    task run_phase(uvm_phase phase);
      item t,a; int id;
      forever begin @(posedge b.clk);
        if(!b.reset_n) begin
          foreach(pending[i]) begin pending[i]=null; a_count[i]=0; d_count[i]=0; end
          a_active=-1; d_active=-1;
        end else begin
          if(b.a_valid) begin t=capture(0); t.check_request(uh); end
          if(b.a_valid && b.a_ready) begin
            id=int'(t.source);
            if(a_active==-1) begin
              if(pending[id]!=null) `uvm_fatal("TL_SOURCE_REUSE","source is busy")
              pending[id]=t; a_active=id;
            end
            a=pending[a_active];
            if({a.opcode,a.param,a.size,a.source,a.address}!={t.opcode,t.param,t.size,t.source,t.address})
              `uvm_fatal("TL_A_MESSAGE_CONTROL","message changed")
            a_count[id]++; if(a_count[id]==a.a_beats()) a_active=-1; publish(t);
          end
          if(b.d_valid) begin
            t=capture(1); id=int'(t.source); a=pending[id];
            if(a==null) begin
              if(!b.a_valid || b.a_source!=b.d_source || a_active!=-1)
                `uvm_fatal("TL_D_WITHOUT_A","unknown source")
              if(b.d_ready) `uvm_fatal("TL_D_BEFORE_A","D accepted before A")
              a=capture(0);
            end
            if(d_count[id]>=a.d_beats()) `uvm_fatal("TL_EXTRA_D","extra response")
            if(d_active!=-1 && d_active!=id) `uvm_fatal("TL_D_INTERLEAVE","interleaved message")
            if(int'(t.opcode)!=a.d_opcode() || t.size!=a.size || t.param!=0 || t.sink)
              `uvm_fatal("TL_D_CONTROL","response mismatch")
            if(t.corrupt && t.opcode!=1 || t.denied && t.opcode==1 && !t.corrupt)
              `uvm_fatal("TL_D_CORRUPT","invalid corrupt flag")
            if(d_count[id]>0 && t.denied!=denied[id]) `uvm_fatal("TL_DENIED_MESSAGE","denied changed")
            if(b.d_ready) begin
              d_count[id]++; denied[id]=t.denied; d_active=id;
              if(d_count[id]==a.d_beats()) d_active=-1; publish(t);
            end
          end
          foreach(pending[i]) if(pending[i]!=null)
            if(a_count[i]==pending[i].a_beats() && d_count[i]==pending[i].d_beats()) begin
              completed++; pending[i]=null; a_count[i]=0; d_count[i]=0;
            end
        end
      end
    endtask
    function void check_phase(uvm_phase phase);
      string idle_reason;
      if(completed==0 && (!uvm_config_db#(string)::get(this,"","idle_reason",idle_reason) || idle_reason.len()==0))
        `uvm_fatal("NO_CHECKS","no_checks: zero completed transactions")
      foreach(pending[i]) if(pending[i]!=null) `uvm_fatal("TL_OUTSTANDING","incomplete message")
    endfunction
  endclass
  class subordinate extends uvm_component;
    `uvm_component_utils(subordinate)
    virtual tilelink_if b;
    memory_model model=new();
    item requests[$],replies[$],queues[16][$];
    int active=-1;
    bit buggy;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual tilelink_if)::get(this,"","bus",b)) `uvm_fatal("TL_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t; bit taken; int start;
      forever begin @(posedge b.clk);
        taken=b.d_valid && b.d_ready;
        if(!b.reset_n) begin
          model=new(); requests.delete(); active=-1;
          foreach(queues[i]) queues[i].delete();
        end else if(b.a_valid && b.a_ready) begin
          t=new(); t.opcode=b.a_opcode; t.param=b.a_param; t.size=b.a_size; t.source=b.a_source;
          t.address=b.a_address; t.mask=b.a_mask; t.data=b.a_data; t.corrupt=b.a_corrupt;
          requests.push_back(t);
          if(requests.size()==requests[0].a_beats()) begin
            model.execute(requests,replies);
            foreach(replies[i]) begin
              if(buggy && replies[i].opcode==1) replies[i].data^=1;
              queues[t.source].push_back(replies[i]);
            end
            requests.delete();
          end
        end
        @(negedge b.clk);
        if(!b.reset_n) begin b.a_ready=0; b.d_valid=0; end
        else begin
          b.a_ready=$urandom_range(0,3)!=0;
          if(taken) b.d_valid=0;
          if(!b.d_valid) begin
            if(active>=0 && queues[active].size()==0) active=-1;
            if(active==-1) begin
              start=int'($urandom_range(0,15));
              for(int j=0;j<16;j++) if(active==-1 && queues[(start+j)%16].size()>0) active=(start+j)%16;
            end
            if(active>=0) begin
              t=queues[active].pop_front(); b.d_valid=1; b.d_opcode=t.opcode; b.d_size=t.size;
              b.d_param=0; b.d_sink=0; b.d_source=t.source; b.d_data=t.data; b.d_denied=t.denied; b.d_corrupt=t.corrupt;
            end
          end
        end
      end
    endtask
  endclass
  class scoreboard extends uvm_component;
    `uvm_component_utils(scoreboard)
    uvm_analysis_imp#(item,scoreboard) input_port;
    memory_model model=new(); item requests[16][$],expected[16][$];
    int count;
    function new(string name,uvm_component parent); super.new(name,parent); input_port=new("input_port",this); endfunction
    function void write(item t);
      item e; item replies[$];
      if(!t.response) begin
        requests[t.source].push_back(t);
        if(requests[t.source].size()==requests[t.source][0].a_beats()) begin
          model.execute(requests[t.source],replies);
          foreach(replies[i]) expected[t.source].push_back(replies[i]); requests[t.source].delete();
        end
      end else begin
        if(expected[t.source].size()==0) `uvm_fatal("TL_MEMORY_DATA","unexpected response")
        e=expected[t.source].pop_front();
        if({e.opcode,e.size,e.data,e.denied,e.corrupt}!={t.opcode,t.size,t.data,t.denied,t.corrupt})
          `uvm_fatal("TL_MEMORY_DATA","memory response mismatch")
        count++;
      end
    endfunction
    function void check_phase(uvm_phase phase);
      if(count==0) `uvm_fatal("TL_NO_TRAFFIC","no responses")
      foreach(expected[i]) if(expected[i].size()>0) `uvm_fatal("TL_OUTSTANDING","missing data")
    endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d; subordinate sub; monitor m; uvm_sequencer#(item) s; bit subordinate_role;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      m=new("m",this); void'(uvm_config_db#(bit)::get(this,"","subordinate_role",subordinate_role));
      if(is_active==UVM_ACTIVE) begin
        if(subordinate_role) sub=new("sub",this); else begin d=new("d",this); s=new("s",this); end
      end
    endfunction
    function void connect_phase(uvm_phase phase); if(d!=null) d.seq_item_port.connect(s.seq_item_export); endfunction
  endclass
endpackage
