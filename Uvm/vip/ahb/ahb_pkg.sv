package ahb_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  function automatic int length(bit [2:0] burst);
    case(burst) 0:return 1; 1:return 0; 2,3:return 4; 4,5:return 8; default:return 16; endcase
  endfunction
  function automatic bit [31:0] next_addr(bit [31:0] addr, bit [2:0] size, burst);
    int boundary;
    boundary=(1<<size)*length(burst);
    if(burst inside {2,4,6}) return (addr & ~(boundary-1)) | ((addr+(1<<size)) & (boundary-1));
    return addr+(1<<size);
  endfunction
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [31:0] address, data[16];
    rand bit write;
    rand bit [2:0] size, burst;
    rand bit [3:0] protection;
    int beats=1, waits;
    bit [31:0] response;
    bit error, aborted;
    constraint legal {size inside {[0:2]}; address inside {[0:63]}; address% (1<<size)==0;}
    function new(string name="item"); super.new(name); endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed"); super.new(name); endfunction
    task body();
      item t;
      for(int sz=0;sz<3;sz++) for(int burst=0;burst<8;burst++) for(int wr=1;wr>=0;wr--) begin
        t=new(); start_item(t); t.size=3'(sz); t.burst=3'(burst); t.write=1'(wr);
        t.address=burst inside {2,4,6} ? (3<<sz) : 0;
        t.beats=length(t.burst); if(t.beats==0) t.beats=5;
        foreach(t.data[i]) t.data[i]=$urandom;
        finish_item(t);
      end
      for(int wr=0;wr<2;wr++) begin
        t=new(); start_item(t); t.address=256; t.write=1'(wr); finish_item(t);
      end
    endtask
  endclass
  class random_sequence extends uvm_sequence#(item);
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body();
      item t;
      repeat(32) begin
        t=new(); start_item(t);
        if(t.randomize()!=1) `uvm_fatal("AHB_RANDOM","randomization failed")
        t.beats=length(t.burst); if(t.beats==0) t.beats=5;
        finish_item(t);
      end
    endtask
  endclass
  class error_sequence extends uvm_sequence#(item);
    `uvm_object_utils(error_sequence)
    function new(string name="error_sequence"); super.new(name); endfunction
    task body();
      item t=new(); start_item(t); t.address=0; t.write=1; t.burst=3; t.beats=4;
      foreach(t.data[i]) t.data[i]=32'(i+1);
      finish_item(t);
    endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual ahb_if b;
    bit inject_address;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual ahb_if)::get(this,"","bus",b)) `uvm_fatal("AHB_CONFIG","missing bus")
    endfunction
    task accept_edge(output bit aborted);
      int waited=0;
      forever begin
        @(posedge b.clk);
        if(!b.reset_n) begin aborted=1; return; end
        if(b.hready) begin aborted=0; return; end
        waited++;
        if(waited>=1000) `uvm_fatal("AHB_TIMEOUT","driver policy limit")
        if(inject_address) begin @(negedge b.clk); b.haddr^=4; end
      end
    endtask
    task run_phase(uvm_phase phase);
      item t; bit aborted; bit [31:0] addr;
      forever begin
        seq_item_port.get_next_item(t); wait(b.reset_n);
        @(negedge b.clk);
        addr=t.address; b.hsel=1; b.htrans=2; b.haddr=addr;
        b.hwrite=t.write; b.hsize=t.size; b.hburst=t.burst; b.hprot=t.protection;
        accept_edge(aborted);
        for(int i=0;i<t.beats && !aborted;i++) begin
          @(negedge b.clk);
          b.hwdata=t.data[i];
          if(i+1<t.beats) begin addr=next_addr(addr,t.size,t.burst); b.haddr=addr; b.htrans=3; end
          else b.htrans=0;
          accept_edge(aborted);
          t.response=b.hrdata; t.error=b.hresp;
        end
        t.aborted=aborted;
        seq_item_port.item_done();
      end
    endtask
  endclass

  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    int observed_transactions;
    virtual ahb_if b;
    uvm_analysis_port#(item) ap;
    item pending, last;
    int beat_count, waits;
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual ahb_if)::get(this,"","bus",b)) `uvm_fatal("AHB_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin
        @(posedge b.clk);
        if(!b.reset_n) begin
          if(pending!=null) begin pending.aborted=1; ap.write(pending); end
          pending=null; last=null; waits=0; beat_count=0;
        end else begin
          if(pending!=null) begin
            if(b.hready) begin
              pending.response=b.hrdata; pending.data[0]=b.hwdata;
              pending.error=b.hresp; pending.waits=waits; if(!pending.aborted) observed_transactions++; ap.write(pending);
              pending=null; waits=0;
            end else waits++;
          end
          if(b.hready) begin
            if(b.hresp && b.htrans!=3) last=null;
            if(!b.hsel || b.htrans==0) begin
              if(last!=null && length(last.burst)!=0 && beat_count<length(last.burst))
                `uvm_fatal("AHB_BURST_SHORT","fixed burst ended early")
              last=null; beat_count=0;
            end else if(b.htrans[1]) begin
              t=new(); t.address=b.haddr; t.write=b.hwrite; t.size=b.hsize;
              t.burst=b.hburst; t.protection=b.hprot;
              if(b.htrans==3) begin
                if(last==null || last.burst==0) `uvm_fatal("AHB_SEQ","missing burst start")
                if({t.write,t.size,t.burst,t.protection}!={last.write,last.size,last.burst,last.protection})
                  `uvm_fatal("AHB_BURST_CONTROL","control changed in burst")
                if(t.address!=next_addr(last.address,last.size,last.burst))
                  `uvm_fatal("AHB_BURST_ADDRESS","wrong next address")
                if(t.address[31:10]!=last.address[31:10]) `uvm_fatal("AHB_1KB","burst crossed boundary")
                beat_count++;
                if(length(t.burst)!=0 && beat_count>length(t.burst)) `uvm_fatal("AHB_BURST_LONG","too many beats")
              end else begin
                if(last!=null && length(last.burst)!=0 && beat_count<length(last.burst))
                  `uvm_fatal("AHB_BURST_SHORT","fixed burst ended early")
                beat_count=1;
              end
              pending=t; last=t;
            end
          end
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
    byte unsigned memory[256];
    int count, errors, waited;
    covergroup traffic with function sample(bit wr, bit err, bit wait_state, bit [2:0] burst,size);
      direction: coverpoint wr;
      response: coverpoint err;
      stalled: coverpoint wait_state;
      bursts: coverpoint burst;
      sizes: coverpoint size {bins supported[]={[0:2]};}
      burst_size: cross bursts,sizes;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); traffic=new(); endfunction
    function void reset_model(); foreach(memory[i]) memory[i]=0; endfunction
    function void write(item t);
      bit expected_error; int lane;
      if(t.aborted) return;
      expected_error=t.address>=256;
      if(t.error!=expected_error) `uvm_fatal("AHB_RESPONSE","error mismatch")
      if(!t.error) begin
        lane=int'(t.address%4);
        for(int i=0;i<(1<<t.size);i++) begin
          if(t.write) memory[t.address+i]=t.data[0][8*(lane+i)+:8];
          else if(t.response[8*(lane+i)+:8]!==memory[t.address+i]) `uvm_fatal("AHB_DATA","read data mismatch")
        end
      end
      count++; if(t.error) errors++; if(t.waits>0) waited++;
      traffic.sample(t.write,t.error,t.waits>0,t.burst,t.size);
    endfunction
  endclass

  // Reactive subordinate uses the same pin-level RAM policy as fixture.sv.
  class subordinate extends uvm_component;
    `uvm_component_utils(subordinate)
    virtual ahb_if b;
    byte unsigned memory[256];
    item pending;
    int remaining;
    bit first_error;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual ahb_if)::get(this,"","bus",b)) `uvm_fatal("AHB_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      bit ready, error; bit [31:0] data; int base,lane;
      forever begin
        @(negedge b.clk); #1;
        ready=1; error=0; data=0;
        if(!b.reset_n) begin
          foreach(memory[i]) memory[i]=0;
          pending=null; remaining=0; first_error=0;
        end else if(pending!=null) begin
          if(remaining>0) ready=0;
          else if(pending.address>=256) begin error=1; ready=first_error; end
          else begin
            base=int'(pending.address & ~3);
            for(int i=0;i<4;i++) data[i*8+:8]=memory[base+i];
          end
        end
        b.hready=ready; b.hresp=error; b.hrdata=data;
        @(posedge b.clk);
        if(b.reset_n) begin
          if(pending!=null) begin
            if(remaining>0) remaining--;
            else if(error && !ready) first_error=1;
            else if(ready && pending.write && !error) begin
              lane=int'(pending.address%4);
              for(int i=0;i<(1<<pending.size);i++) memory[pending.address+i]=b.hwdata[8*(lane+i)+:8];
            end
          end
          if(ready) begin
            pending=null; first_error=0;
            if(b.hsel && b.htrans[1]) begin
              pending=new(); pending.address=b.haddr; pending.write=b.hwrite; pending.size=b.hsize;
              remaining=$urandom_range(0,3);
            end
          end
        end
      end
    endtask
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
    function void connect_phase(uvm_phase phase); if(d!=null) d.seq_item_port.connect(s.seq_item_export); endfunction
  endclass
endpackage
