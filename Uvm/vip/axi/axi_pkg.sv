package axi_vip;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  typedef enum {AW,W,B,AR,R} channel;
  class item extends uvm_sequence_item;
    `uvm_object_utils(item)
    channel ch;
    rand bit [31:0] address,data;
    rand bit [3:0] id,strobe;
    bit [7:0] len;
    bit [2:0] size=2,prot;
    bit [3:0] cache;
    bit [1:0] burst=1,resp;
    bit lock,last=1;
    function new(string name="item"); super.new(name); endfunction
    function int unsigned addr(int i);
      int unsigned span,value;
      span=(int'(len)+1)*(1<<size);
      value=address+(burst==0 ? 0 : i*(1<<size));
      return burst==2 ? (address/span)*span+value%span : value;
    endfunction
    function void check_address(bit lite=0);
      if(size>2 || burst==3 || address%(1<<size)!=0)
        `uvm_fatal("AXI_ADDRESS_PROFILE","unsupported address")
      if((burst==0 && len>15) || (burst==2 && !(len inside {1,3,7,15})))
        `uvm_fatal("AXI_BURST_LENGTH","invalid burst")
      for(int i=0;i<=int'(len);i++) if(addr(i)/4096!=address/4096)
        `uvm_fatal("AXI_4K_BOUNDARY","burst crosses boundary")
      if(lock && (!(len inside {0,1,3,7,15}) || address%((int'(len)+1)*(1<<size))!=0))
        `uvm_fatal("AXI_EXCLUSIVE_ALIGNMENT","exclusive alignment")
      if(lite && (id || len || lock || size!=2 || burst!=1 || cache))
        `uvm_fatal("AXIL_PROFILE","not Lite")
    endfunction
  endclass
  class directed extends uvm_sequence#(item);
    `uvm_object_utils(directed)
    bit lite;
    function new(string name="directed"); super.new(name); endfunction
    task send(channel ch,int ident,int length,int burst_kind,int value=0,bit final_beat=1,bit exclusive=0);
      item t=new(); start_item(t); t.ch=ch; t.id=4'(ident); t.len=8'(length);
      t.burst=2'(burst_kind); t.address='h100; t.data=32'(value); t.strobe=15;
      t.last=final_beat; t.lock=exclusive; finish_item(t);
    endtask
    task body();
      for(int burst_kind=0;burst_kind<3;burst_kind++) begin
        if(lite && burst_kind!=1) continue;
        send(AW,0,lite ? 0 : 3,burst_kind);
        for(int i=0;i<(lite ? 1 : 4);i++) send(W,0,0,1,i+1,lite || i==3);
        send(AR,0,lite ? 0 : 3,burst_kind);
      end
      if(!lite) begin
        // Multiple IDs, then an exclusive read/write pair.
        send(AR,1,0,1); send(AR,2,0,1);
        send(AR,3,0,1,0,1,1);
      end
    endtask
  endclass
  class random_sequence extends directed;
    `uvm_object_utils(random_sequence)
    function new(string name="random_sequence"); super.new(name); endfunction
    task body();
      repeat(32) begin
        send(AW,0,0,1); send(W,0,0,1,int'($urandom)); send(AR,0,0,1);
      end
    endtask
  endclass
  class error_sequence extends directed;
    `uvm_object_utils(error_sequence)
    function new(string name="error_sequence"); super.new(name); endfunction
    task body(); send(AW,0,0,1); send(W,0,0,1,42,0); endtask
  endclass
  class driver extends uvm_driver#(item);
    `uvm_component_utils(driver)
    virtual axi_if b;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual axi_if)::get(this,"","bus",b)) `uvm_fatal("AXI_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item t; int waited; bit done;
      b.bready=1; b.rready=1;
      forever begin
        seq_item_port.get_next_item(t); wait(b.reset_n); @(negedge b.clk);
        case(t.ch)
          AW: begin b.awvalid=1; b.awaddr=t.address; b.awid=t.id; b.awlen=t.len;
            b.awsize=t.size; b.awburst=t.burst; b.awlock=t.lock; b.awprot=t.prot; b.awcache=t.cache; end
          W: begin b.wvalid=1; b.wdata=t.data; b.wstrb=t.strobe; b.wlast=t.last; end
          AR: begin b.arvalid=1; b.araddr=t.address; b.arid=t.id; b.arlen=t.len;
            b.arsize=t.size; b.arburst=t.burst; b.arlock=t.lock; b.arprot=t.prot; b.arcache=t.cache; end
          default: `uvm_fatal("AXI_ROLE","manager sequence must use AW/W/AR")
        endcase
        waited=0;
        forever begin
          @(posedge b.clk);
          done=(t.ch==AW ? b.awready : t.ch==W ? b.wready : b.arready);
          if(!b.reset_n || done) break;
          if(++waited>=1000) `uvm_fatal("AXI_TIMEOUT","manager policy timeout")
        end
        @(negedge b.clk);
        case(t.ch) AW:b.awvalid=0; W:b.wvalid=0; AR:b.arvalid=0; default:; endcase
        seq_item_port.item_done();
      end
    endtask
  endclass
  // Observe channels independently. Per-ID queues check response order and lengths.
  class monitor extends uvm_component;
    `uvm_component_utils(monitor)
    virtual axi_if b;
    uvm_analysis_port#(item) ap;
    item aws[$],ws[$],writes[16][$],reads[16][$];
    int read_index[16];
    bit lite;
    int count;
    covergroup traffic with function sample(int ch,int id,int len,int burst_kind,int resp,bit lock);
      channels:coverpoint ch; ids:coverpoint id; lengths:coverpoint len;
      bursts:coverpoint burst_kind; responses:coverpoint resp; exclusives:coverpoint lock;
      routing:cross channels,ids;
    endgroup
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); traffic=new(); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual axi_if)::get(this,"","bus",b)) `uvm_fatal("AXI_CONFIG","missing bus")
      void'(uvm_config_db#(bit)::get(this,"","lite",lite));
    endfunction
    function item capture(channel ch);
      item t=new(); t.ch=ch;
      case(ch)
        AW,AR:begin
          t.address=ch==AW ? b.awaddr : b.araddr; t.id=ch==AW ? b.awid : b.arid;
          t.len=ch==AW ? b.awlen : b.arlen; t.size=ch==AW ? b.awsize : b.arsize;
          t.burst=ch==AW ? b.awburst : b.arburst; t.lock=ch==AW ? b.awlock : b.arlock;
          t.prot=ch==AW ? b.awprot : b.arprot; t.cache=ch==AW ? b.awcache : b.arcache;
          t.check_address(lite);
        end
        W:begin t.data=b.wdata; t.strobe=b.wstrb; t.last=b.wlast; end
        B:begin t.id=b.bid; t.resp=b.bresp; end
        R:begin t.id=b.rid; t.resp=b.rresp; t.data=b.rdata; t.last=b.rlast; end
      endcase
      return t;
    endfunction
    function void publish(item t);
      count++; traffic.sample(int'(t.ch),int'(t.id),int'(t.len),int'(t.burst),int'(t.resp),t.lock); ap.write(t);
    endfunction
    task run_phase(uvm_phase phase);
      item t,a,w; int mask;
      forever begin
        @(posedge b.clk);
        if(!b.reset_n) begin
          aws.delete(); ws.delete();
          foreach(reads[i]) begin reads[i].delete(); writes[i].delete(); read_index[i]=0; end
        end else begin
          if(b.bvalid) begin
            if(writes[b.bid].size()==0) `uvm_fatal("AXI_B_WITHOUT_WRITE","unknown BID")
            a=writes[b.bid][0];
            if(b.bresp==1 && (!a.lock || lite)) `uvm_fatal("AXI_RESPONSE","unexpected EXOKAY")
            if(b.bready) begin t=capture(B); a=writes[b.bid].pop_front(); publish(t); end
          end
          if(b.rvalid) begin
            if(reads[b.rid].size()==0) `uvm_fatal("AXI_R_WITHOUT_READ","unknown RID")
            a=reads[b.rid][0];
            if(b.rresp==1 && (!a.lock || lite)) `uvm_fatal("AXI_RESPONSE","unexpected EXOKAY")
            if(b.rlast!=(read_index[b.rid]==int'(a.len))) `uvm_fatal("AXI_RLAST","read burst length")
            if(b.rready) begin
              t=capture(R); publish(t);
              if(t.last) begin a=reads[t.id].pop_front(); read_index[t.id]=0; end
              else read_index[t.id]++;
            end
          end
          if(b.awvalid && b.awready) begin t=capture(AW); aws.push_back(t); publish(t); end
          if(b.arvalid && b.arready) begin t=capture(AR); reads[t.id].push_back(t); publish(t); end
          if(b.wvalid && b.wready) begin t=capture(W); ws.push_back(t); publish(t); end
          while(aws.size()>0 && ws.size()>int'(aws[0].len)) begin
            a=aws.pop_front();
            for(int i=0;i<=int'(a.len);i++) begin
              w=ws.pop_front();
              if(w.last!=(i==int'(a.len))) `uvm_fatal("AXI_WLAST","write burst length")
              mask=((1<<(1<<a.size))-1)<<(a.addr(i)%4);
              if((int'(w.strobe)&~mask)!=0) `uvm_fatal("AXI_WSTRB_LANE","strobe outside transfer")
            end
            writes[a.id].push_back(a);
          end
        end
      end
    endtask
    function void check_phase(uvm_phase phase);
      if(aws.size() || ws.size()) `uvm_fatal("AXI_OUTSTANDING","incomplete write")
      foreach(reads[i]) if(reads[i].size() || writes[i].size()) `uvm_fatal("AXI_OUTSTANDING","missing response")
    endfunction
  endclass
  class subordinate extends uvm_component;
    `uvm_component_utils(subordinate)
    virtual axi_if b;
    item aws[$],ws[$],bs[16][$],rs[16][$];
    item reservations[16];
    bit [7:0] memory[int unsigned];
    bit buggy;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      if(!uvm_config_db#(virtual axi_if)::get(this,"","bus",b)) `uvm_fatal("AXI_CONFIG","missing bus")
    endfunction
    task run_phase(uvm_phase phase);
      item a,w,t; bit success; int addr,ident; bit found,b_taken,r_taken;
      forever begin
        @(posedge b.clk);
        b_taken=b.bvalid && b.bready; r_taken=b.rvalid && b.rready;
        if(!b.reset_n) begin
          aws.delete(); ws.delete(); memory.delete();
          foreach(rs[i]) begin rs[i].delete(); bs[i].delete(); reservations[i]=null; end
        end else begin
          if(b.awvalid && b.awready) begin
            a=new(); a.address=b.awaddr; a.id=b.awid; a.len=b.awlen; a.size=b.awsize;
            a.burst=b.awburst; a.lock=b.awlock; aws.push_back(a);
          end
          if(b.wvalid && b.wready) begin
            w=new(); w.data=b.wdata; w.strobe=b.wstrb; ws.push_back(w);
          end
          if(b.arvalid && b.arready) begin
            a=new(); a.address=b.araddr; a.id=b.arid; a.len=b.arlen; a.size=b.arsize;
            a.burst=b.arburst; a.lock=b.arlock;
            if(a.lock) reservations[a.id]=a;
            for(int i=0;i<=int'(a.len);i++) begin
              t=new(); t.id=a.id; t.last=i==int'(a.len); t.resp=a.lock ? 1 : 0;
              addr=int'(a.addr(i))&~3;
              for(int lane=0;lane<4;lane++) t.data[8*lane+:8]=memory.exists(addr+lane) ? memory[addr+lane] : 0;
              if(buggy) t.data^=1;
              rs[t.id].push_back(t);
            end
          end
          while(aws.size()>0 && ws.size()>int'(aws[0].len)) begin
            a=aws.pop_front(); t=new(); t.id=a.id;
            success=!a.lock;
            if(a.lock && reservations[a.id]!=null)
              success=reservations[a.id].address==a.address && reservations[a.id].size==a.size && reservations[a.id].len==a.len;
            t.resp=a.lock && success ? 1 : 0;
            for(int i=0;i<=int'(a.len);i++) begin
              w=ws.pop_front(); addr=int'(a.addr(i))&~3;
              if(success) for(int lane=0;lane<4;lane++) if(w.strobe[lane]) begin
                memory[addr+lane]=w.data[8*lane+:8];
                foreach(reservations[j]) if(reservations[j]!=null)
                  if((addr+lane)>=int'(reservations[j].address) &&
                    (addr+lane)<int'(reservations[j].address)+(int'(reservations[j].len)+1)*(1<<reservations[j].size)) reservations[j]=null;
              end
            end
            reservations[a.id]=null; bs[t.id].push_back(t);
          end

        end
        @(negedge b.clk);
        if(!b.reset_n) begin b.awready=0; b.wready=0; b.arready=0; b.bvalid=0; b.rvalid=0; end
        else begin
          if(b_taken) b.bvalid=0;
          if(r_taken) b.rvalid=0;
          b.awready=$urandom_range(0,3)!=0; b.wready=$urandom_range(0,3)!=0; b.arready=$urandom_range(0,3)!=0;
          if(!b.bvalid) begin
            ident=int'($urandom_range(0,15)); found=0;
            for(int j=0;j<16;j++) if(!found && bs[(ident+j)%16].size()>0) begin
              t=bs[(ident+j)%16].pop_front(); b.bvalid=1; b.bid=t.id; b.bresp=t.resp; found=1;
            end
          end
          if(!b.rvalid) begin
            ident=int'($urandom_range(0,15)); found=0;
            for(int j=0;j<16;j++) if(!found && rs[(ident+j)%16].size()>0) begin
              t=rs[(ident+j)%16].pop_front(); b.rvalid=1; b.rid=t.id; b.rresp=t.resp; b.rdata=t.data; b.rlast=t.last; found=1;
            end
          end
        end
      end
    endtask
  endclass
  class scoreboard extends uvm_component;
    `uvm_component_utils(scoreboard)
    uvm_analysis_imp#(item,scoreboard) input_port;
    bit [7:0] memory[int unsigned];
    item aws[$],ws[$],expected[16][$];
    int count;
    function new(string name,uvm_component parent);
      super.new(name,parent); input_port=new("input_port",this);
    endfunction
    function void write(item t);
      item a,w,e; int addr;
      case(t.ch)
        AW: aws.push_back(t);
        W: ws.push_back(t);
        AR: for(int i=0;i<=int'(t.len);i++) begin
          e=new(); addr=int'(t.addr(i))&~3;
          for(int lane=0;lane<4;lane++) e.data[8*lane+:8]=memory.exists(addr+lane) ? memory[addr+lane] : 0;
          expected[t.id].push_back(e);
        end
        R: begin
          if(expected[t.id].size()==0) `uvm_fatal("AXI_READ_DATA","unexpected read")
          e=expected[t.id].pop_front();
          if(t.resp<2 && t.data!=e.data) `uvm_fatal("AXI_READ_DATA","read differs from memory")
          count++;
        end
        default:;
      endcase
      while(aws.size()>0 && ws.size()>int'(aws[0].len)) begin
        a=aws.pop_front();
        // This scoreboard fixture uses ordinary writes only. Projects can
        // connect their own scoreboard for exclusive and error responses.
        if(a.lock) `uvm_fatal("AXI_SCOREBOARD_PROFILE","exclusive write needs project scoreboard")
        for(int i=0;i<=int'(a.len);i++) begin
          w=ws.pop_front(); addr=int'(a.addr(i))&~3;
          for(int lane=0;lane<4;lane++) if(w.strobe[lane]) memory[addr+lane]=w.data[8*lane+:8];
        end
      end
    endfunction
    function void check_phase(uvm_phase phase);
      if(count==0) `uvm_fatal("AXI_MISSING_READ","no checked read")
      foreach(expected[i]) if(expected[i].size()>0) `uvm_fatal("AXI_MISSING_READ","missing read response")
    endfunction
  endclass
  class agent extends uvm_agent;
    `uvm_component_utils(agent)
    driver d; subordinate sub; monitor m; uvm_sequencer#(item) s;
    bit subordinate_role;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
      m=new("m",this);
      void'(uvm_config_db#(bit)::get(this,"","subordinate_role",subordinate_role));
      if(is_active==UVM_ACTIVE) begin
        if(subordinate_role) sub=new("sub",this);
        else begin d=new("d",this); s=new("s",this); end
      end
    endfunction
    function void connect_phase(uvm_phase phase); if(d!=null) d.seq_item_port.connect(s.seq_item_export); endfunction
  endclass
endpackage
