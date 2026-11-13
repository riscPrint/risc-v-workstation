package spi_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  `uvm_analysis_imp_decl(_input)
  `uvm_analysis_imp_decl(_output)
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [31:0] mosi;
    bit [31:0] miso;
    bit abort_word;
    function new(string name="item"); super.new(name); endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    int bits=8;
    function new(string name="directed"); super.new(name); endfunction
    task body(); item t;
      for(int i=0;i<4;i++) begin t=new(); start_item(t);
        case(i) 0:t.mosi=0; 1:t.mosi='1; 2:t.mosi='h55555555; 3:t.mosi='haaaaaaaa; endcase
        t.mosi&=32'((64'b1<<bits)-1); finish_item(t);
      end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body(); item t;
      repeat(32) begin t=new(); start_item(t); t.mosi=$urandom&32'((64'b1<<bits)-1); finish_item(t); end
    endtask
  endclass
  class error_sequence extends uvm_sequence#(item);
    `uvm_object_utils(error_sequence)
    function new(string name="error_sequence"); super.new(name); endfunction
    task body(); item t=new(); start_item(t); t.mosi=42; t.abort_word=1; finish_item(t); endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual spi_if b;
    uvm_analysis_port#(item) expected;
    function new(string name,uvm_component parent); super.new(name,parent); expected=new("expected",this); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual spi_if)::get(this,"","bus",b)) `uvm_fatal("SPI_CONFIG","missing bus")
    endfunction
    task hold_cycles(); repeat(3) @(negedge b.clk); endtask
    task run_phase(uvm_phase phase);
      item t,e; int index;
      forever begin
        seq_item_port.get_next_item(t); wait(b.reset_n);
        e=new(); e.mosi=t.mosi; e.miso=t.mosi; expected.write(e);
        @(negedge b.clk); b.sclk=b.polarity; hold_cycles(); b.cs_n=0; hold_cycles();
        for(int i=0;i<b.bits;i++) begin
          if(t.abort_word && i==b.bits/2) break;
          index=b.lsb_first ? i : b.bits-1-i; b.mosi=t.mosi[index]; hold_cycles();
          b.sclk=!b.polarity; hold_cycles(); b.sclk=b.polarity; hold_cycles();
        end
        b.cs_n=1; hold_cycles(); seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    int observed_transactions;
    virtual spi_if b; uvm_analysis_port#(item) ap;
    bit old_cs=1,old_clk; int index,count; bit [31:0] tx,rx;
    covergroup traffic with function sample(bit polarity,phase,lsb,int bits,int data);
      polarities:coverpoint polarity; phases:coverpoint phase; orders:coverpoint lsb;
      widths:coverpoint bits; words:coverpoint data; modes:cross polarities,phases;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); traffic=new(); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual spi_if)::get(this,"","bus",b)) `uvm_fatal("SPI_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t; int lane;
      forever begin @(posedge b.clk);
        if(!b.reset_n) begin index=0; tx=0; rx=0; end
        else begin
          if(b.bits<1 || b.bits>32) `uvm_fatal("SPI_CONFIG","invalid width")
          if(b.cs_n && !old_cs && index!=0) `uvm_fatal("SPI_PARTIAL_WORD","select ended early")
          if(!b.cs_n && old_cs && b.sclk!=b.polarity) `uvm_fatal("SPI_SELECT_CLOCK","non-idle select")
          if(!b.cs_n && b.sclk!=old_clk && b.sclk==(b.phase ? b.polarity : !b.polarity)) begin
            lane=b.lsb_first ? index : b.bits-1-index; tx[lane]=b.mosi; rx[lane]=b.miso; index++;
            if(index==b.bits) begin
              t=new(); t.mosi=tx; t.miso=rx; observed_transactions++; ap.write(t); count++;
              traffic.sample(b.polarity,b.phase,b.lsb_first,b.bits,int'(tx)); index=0; tx=0; rx=0;
            end
          end
        end
        old_cs=b.cs_n; old_clk=b.sclk;
      end
    endtask
    function void check_phase(uvm_phase phase);
      string idle_reason;
      if(observed_transactions==0 && (!uvm_config_db#(string)::get(this,"","idle_reason",idle_reason) || idle_reason.len()==0))
        `uvm_fatal("NO_CHECKS","no_checks: zero observed transactions")

      if(index!=0 || !b.cs_n) `uvm_fatal("SPI_UNFINISHED_SELECT","incomplete transfer")
    endfunction
  endclass
  class subordinate extends uvm_component;
    `uvm_component_utils(subordinate)
    virtual spi_if b;
    bit [31:0] words[$]; bit [31:0] word_value; bit old_cs=1,old_clk;
    int index;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual spi_if)::get(this,"","bus",b)) `uvm_fatal("SPI_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      bit [31:0] discarded; int lane;
      forever begin
        @(posedge b.clk);
        if(!b.reset_n || b.cs_n) index=0;
        else if(b.sclk!=old_clk && b.sclk==(b.phase ? b.polarity : !b.polarity)) begin
          index++;
          if(index==b.bits) begin if(words.size()>0) discarded=words.pop_front(); index=0; end
        end
        old_cs=b.cs_n; old_clk=b.sclk;
        @(negedge b.clk);
        word_value=words.size()>0 ? words[0] : '1;
        lane=b.lsb_first ? index : b.bits-1-index;
        b.miso=b.reset_n && !b.cs_n ? word_value[lane] : 0;
      end
    endtask
  endclass
  class scoreboard extends uvm_component;
    `uvm_component_utils(scoreboard)
    uvm_analysis_imp_input#(item,scoreboard) input_port;
    uvm_analysis_imp_output#(item,scoreboard) output_port;
    item expected[$]; int count;
    function new(string name,uvm_component parent);
      super.new(name,parent); input_port=new("input_port",this); output_port=new("output_port",this);
    endfunction
    function void write_input(item t); expected.push_back(t); endfunction
    function void write_output(item t);
      item e;
      if(expected.size()==0) `uvm_fatal("SPI_WORD_STREAM","unexpected word")
      e=expected.pop_front();
      if({e.mosi,e.miso}!={t.mosi,t.miso}) `uvm_fatal("SPI_WORD_STREAM","word mismatch")
      count++;
    endfunction
    function void check_phase(uvm_phase phase);
      if(count==0 || expected.size()>0) `uvm_fatal("SPI_MISSING_WORD","missing transfer")
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
