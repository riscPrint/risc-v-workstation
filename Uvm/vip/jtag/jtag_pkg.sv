package jtag_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  `uvm_analysis_imp_decl(_expected)
  `uvm_analysis_imp_decl(_observed)
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [63:0] data;rand bit ir;int bits=8;
    function new(string name="item");super.new(name);endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    function new(string name="directed");super.new(name);endfunction
    task body();item t;
      for(int i=0;i<4;i++)begin t=new();start_item(t);t.data=64'(i*85);t.ir=i[0];finish_item(t);end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence");super.new(name);endfunction
    task body();item t;repeat(32)begin t=new();start_item(t);t.data=64'($urandom)&255;t.ir=1'($urandom);finish_item(t);end endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual jtag_if b;uvm_analysis_port#(item) expected;
    function new(string name,uvm_component parent);super.new(name,parent);expected=new("expected",this);endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual jtag_if)::get(this,"","bus",b)) `uvm_fatal("JTAG_CONFIG","missing bus")
    endfunction
    task pulse(bit tms,tdi=0);
      @(negedge b.clk);b.tck=0;b.tms=tms;b.tdi=tdi;
      @(negedge b.clk);b.tck=1;@(negedge b.clk);b.tck=0;
    endtask
    task run_phase(uvm_phase phase);item t;
      forever begin seq_item_port.get_next_item(t);
        if(t.bits<1 || t.bits>64) `uvm_fatal("JTAG_CONFIG","scan width")
        expected.write(t);repeat(5)pulse(1);pulse(0);pulse(1);
        if(t.ir)pulse(1);pulse(0);pulse(0);
        for(int i=0;i<t.bits;i++)pulse(i==t.bits-1,t.data[i]);
        pulse(1);pulse(0);seq_item_port.item_done();
      end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual jtag_if b;uvm_analysis_port#(item) ap;
    int state,count;bit [63:0] data;
    int next0[16]='{1,1,3,4,4,6,6,4,1,10,11,11,13,13,11,1};
int next1[16]='{0,2,9,5,5,8,7,8,2,0,12,12,15,14,15,2};
    covergroup traffic with function sample(int state,bits);
      states:coverpoint state;widths:coverpoint bits;
    endgroup
    function new(string name,uvm_component parent);super.new(name,parent);ap=new("ap",this);traffic=new();endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual jtag_if)::get(this,"","bus",b)) `uvm_fatal("JTAG_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);item t;
      forever begin @(posedge b.tck or negedge b.trst_n);
        if(!b.trst_n)begin state=0;count=0;data=0;end
        else begin
          if(state==4 || state==11)begin
            if(count>=64) `uvm_fatal("JTAG_SCAN_WIDTH","scan exceeds profile")
            data[count]=b.tdo;count++;
            if(b.tms)begin t=new();t.data=data;t.bits=count;t.ir=state==11;ap.write(t);traffic.sample(state,count);count=0;data=0;end
          end
          state=b.tms ? next1[state] : next0[state];
        end
      end
    endtask
    function void check_phase(uvm_phase phase);if(count!=0) `uvm_fatal("JTAG_UNFINISHED_SCAN","partial scan") endfunction
  endclass
  class scoreboard extends uvm_component;
    `uvm_component_utils(scoreboard)
    uvm_analysis_imp_expected#(item,scoreboard) input_port;
    uvm_analysis_imp_observed#(item,scoreboard) output_port;
    item expected[$];int count;
    function new(string name,uvm_component parent);super.new(name,parent);input_port=new("input_port",this);output_port=new("output_port",this);endfunction
    function void write_expected(item t);expected.push_back(t);endfunction
    function void write_observed(item t);item e;
      if(expected.size()==0) `uvm_fatal("JTAG_SCAN_DATA","unexpected scan")
      e=expected.pop_front();
      if(e.bits!=t.bits || e.ir!=t.ir || (e.data&((64'b1<<e.bits)-1))!=t.data) `uvm_fatal("JTAG_SCAN_DATA","scan mismatch")
      count++;
    endfunction
    function void check_phase(uvm_phase phase);if(count==0 || expected.size()>0) `uvm_fatal("JTAG_NO_SCANS","missing scan") endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d;monitor m;uvm_sequencer#(item) s;
    function new(string name,uvm_component parent);super.new(name,parent);endfunction
    function void build_phase(uvm_phase phase);m=new("m",this);if(is_active==UVM_ACTIVE)begin d=new("d",this);s=new("s",this);end endfunction
    function void connect_phase(uvm_phase phase);if(d!=null)d.seq_item_port.connect(s.seq_item_export);endfunction
  endclass
endpackage
