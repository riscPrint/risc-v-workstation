package uart_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  `uvm_analysis_imp_decl(_input)
  `uvm_analysis_imp_decl(_output)
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    rand bit [8:0] data;
    bit parity_error,framing_error;
    function new(string name="item"); super.new(name); endfunction
  endclass
  task automatic send_frame(virtual uart_if b,item t,bit subordinate_role);
    bit bits[$],parity;
    bits.push_back(0); parity=0;
    for(int i=0;i<b.data_bits;i++) begin bits.push_back(t.data[i]); parity^=t.data[i]; end
    if(b.parity!=0) bits.push_back(parity^(b.parity==2)^t.parity_error);
    repeat(b.stop_bits) bits.push_back(!t.framing_error);
    foreach(bits[i]) repeat(b.cycles_per_bit) begin
      @(negedge b.clk);
      if(!b.reset_n) begin if(subordinate_role) b.rx=1; else b.tx=1; return; end
      if(subordinate_role) b.rx=bits[i]; else b.tx=bits[i];
    end
    repeat(b.cycles_per_bit) begin @(negedge b.clk); if(subordinate_role) b.rx=1; else b.tx=1; end
  endtask
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    int data_bits=8;
    function new(string name="directed"); super.new(name); endfunction
    task body();
      item t;
      for(int i=0;i<4;i++) begin
        t=new(); start_item(t);
        case(i) 0:t.data=0; 1:t.data=9'((1<<data_bits)-1); 2:t.data=9'h55; 3:t.data=9'hAA; endcase
        t.data&=9'((1<<data_bits)-1); finish_item(t);
      end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body(); item t;
      repeat(32) begin t=new(); start_item(t); t.data=9'($urandom)&9'((1<<data_bits)-1); finish_item(t); end
    endtask
  endclass
  class error_sequence extends uvm_sequence#(item);
    `uvm_object_utils(error_sequence)
    function new(string name="error_sequence"); super.new(name); endfunction
    task body(); item t=new(); start_item(t); t.data=42; t.parity_error=1; t.framing_error=1; finish_item(t); endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual uart_if b; bit subordinate_role;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual uart_if)::get(this,"","bus",b)) `uvm_fatal("UART_CONFIG","missing bus")
      void'(uvm_config_db#(bit)::get(this,"","subordinate_role",subordinate_role));
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin seq_item_port.get_next_item(t); wait(b.reset_n); send_frame(b,t,subordinate_role); seq_item_port.item_done(); end
    endtask
  endclass
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual uart_if b; bit observe_tx;
    uvm_analysis_port#(item) ap;
    int state,remaining,index,count;
    bit [8:0] data;
    bit parity_error,framing_error;
    covergroup traffic with function sample(int data,bit parity_error,bit framing_error);
      bytes_seen:coverpoint data; parity_errors:coverpoint parity_error; framing_errors:coverpoint framing_error;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); traffic=new(); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual uart_if)::get(this,"","bus",b)) `uvm_fatal("UART_CONFIG","missing bus")
      void'(uvm_config_db#(bit)::get(this,"","observe_tx",observe_tx));
    endfunction
    task run_phase(uvm_phase phase);
      bit line,expected; item t;
      forever begin @(posedge b.clk); line=observe_tx ? b.tx : b.rx;
        if(!b.reset_n) begin state=0; data=0; index=0; parity_error=0; framing_error=0; end
        else if(state==5) begin if(line) state=0; end
        else if(state==0) begin if(!line) begin state=1; remaining=b.cycles_per_bit/2; end end
        else begin
          remaining--;
          if(remaining==0) begin
            remaining=b.cycles_per_bit;
            case(state)
              1:begin if(line) state=0; else begin state=2; data=0; index=0; parity_error=0; framing_error=0; end end
              2:begin
                data[index]=line; index++;
                if(index==b.data_bits) begin state=b.parity==0 ? 4 : 3; index=0; end
              end
              3:begin
                expected=0; for(int i=0;i<b.data_bits;i++) expected^=data[i];
                expected^=(b.parity==2); parity_error=line!=expected; state=4;
              end
              4:begin
                framing_error|=!line; index++;
                if(index==b.stop_bits) begin
                  t=new(); t.data=data; t.parity_error=parity_error; t.framing_error=framing_error;
                  traffic.sample(int'(data),parity_error,framing_error); ap.write(t); count++;
                  state=framing_error ? 5 : 0;
                end
              end
              default:state=0;
            endcase
          end
        end
      end
    endtask
  endclass
  class subordinate extends uvm_component;
    `uvm_component_utils(subordinate)
    virtual uart_if b;
    uvm_tlm_analysis_fifo#(item) fifo;
    bit buggy;
    function new(string name,uvm_component parent); super.new(name,parent); fifo=new("fifo",this); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual uart_if)::get(this,"","bus",b)) `uvm_fatal("UART_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t;
      forever begin
        fifo.get(t); repeat($urandom_range(0,3)*b.cycles_per_bit) @(posedge b.clk);
        if(buggy) t.data^=1; send_frame(b,t,1);
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
    function void write_input(item t);
      item copy=new(); copy.data=t.data; copy.parity_error=t.parity_error; copy.framing_error=t.framing_error; expected.push_back(copy);
    endfunction
    function void write_output(item t);
      item e;
      if(expected.size()==0) `uvm_fatal("UART_BYTE_STREAM","unexpected frame")
      e=expected.pop_front();
      if({e.data,e.parity_error,e.framing_error}!={t.data,t.parity_error,t.framing_error}) `uvm_fatal("UART_BYTE_STREAM","frame mismatch")
      count++;
    endfunction
    function void check_phase(uvm_phase phase);
      if(expected.size()>0 || count==0) `uvm_fatal("UART_MISSING_FRAME","undrained frame stream")
    endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d; subordinate sub; monitor m; uvm_sequencer#(item) s; bit subordinate_role;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      void'(uvm_config_db#(bit)::get(this,"","subordinate_role",subordinate_role));
      uvm_config_db#(bit)::set(this,"m","observe_tx",subordinate_role);
      m=new("m",this);
      if(is_active==UVM_ACTIVE) begin
        if(subordinate_role) sub=new("sub",this); else begin d=new("d",this); s=new("s",this); end
      end
    endfunction
    function void connect_phase(uvm_phase phase);
      if(d!=null) d.seq_item_port.connect(s.seq_item_export);
      if(sub!=null) m.ap.connect(sub.fifo.analysis_export);
    endfunction
  endclass
endpackage
