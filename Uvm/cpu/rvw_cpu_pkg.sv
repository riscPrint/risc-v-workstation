package rvw_cpu_pkg;
 import uvm_pkg::*;
 `include "uvm_macros.svh"
 import "DPI-C" function int rvw_uvm_check(input longint unsigned data[]);
 import "DPI-C" function string rvw_uvm_error();
 import "DPI-C" function int rvw_uvm_check_state(input longint unsigned gprs[], csr_addresses[], csr_values[], input int unsigned csr_count);
 class cpu_retirement extends uvm_sequence_item;
  `uvm_object_utils(cpu_retirement)
  longint unsigned order, values[19], gprs[32], csr_addresses[8], csr_values[8];
  int unsigned csr_count;
  bit state_valid;
  function new(string name="cpu_retirement"); super.new(name); endfunction
 endclass
 class cpu_monitor extends uvm_monitor;
  `uvm_component_utils(cpu_monitor)
  virtual rvw_cpu_if vif;
  longint unsigned cycle;
  uvm_analysis_port #(cpu_retirement) ap;
  function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); endfunction
  function void build_phase(uvm_phase phase);
   if(!uvm_config_db#(virtual rvw_cpu_if)::get(this,"","vif",vif))
    `uvm_fatal("CPU_BINDING","project rvw_cpu_if required")
  endfunction
  task run_phase(uvm_phase phase);
   forever begin
    @(negedge vif.clk); cycle++;
    if(vif.reset_n && vif.rvfi_valid) begin
     cpu_retirement t=new(); t.order=vif.rvfi_order; t.values=vif.retirement;
     t.state_valid=vif.state_valid;
     if(t.state_valid) begin
      if(vif.csr_count>8) `uvm_fatal("CSR_BINDING","at most eight CSR observations per retirement")
      t.gprs=vif.gpr_state;
      t.csr_count=vif.csr_count;
      t.csr_addresses=vif.csr_addresses; t.csr_values=vif.csr_values;
     end
     ap.write(t);
     $write("RVW_CPU_RETIRE %0d %0d",t.order,cycle);
     foreach(t.values[i]) $write(" %0h",t.values[i]);
     $write("\n");
    end
   end
  endtask
 endclass
 class cpu_scoreboard extends uvm_subscriber #(cpu_retirement);
  `uvm_component_utils(cpu_scoreboard)
  longint unsigned checks;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void write(cpu_retirement t);
   int rc;
   if(t.order!=checks) `uvm_fatal("RVFI_ORDER","retirement gap or duplicate")
   rc=rvw_uvm_check(t.values);
   if(rc==1) `uvm_fatal("SPIKE_MISMATCH",rvw_uvm_error())
   if(rc!=0) `uvm_fatal("SPIKE_ERROR",rvw_uvm_error())
   if(t.state_valid) begin
    rc=rvw_uvm_check_state(t.gprs,t.csr_addresses,t.csr_values,t.csr_count);
    if(rc==1) `uvm_fatal("SPIKE_MISMATCH",rvw_uvm_error())
    if(rc!=0) `uvm_fatal("SPIKE_ERROR",rvw_uvm_error())
   end
   checks++;
  endfunction
  function void check_phase(uvm_phase phase);
   if(checks==0) `uvm_error("NO_CHECKS","no CPU retirements compared")
  endfunction
 endclass
 class cpu_coverage extends uvm_subscriber #(cpu_retirement);
  `uvm_component_utils(cpu_coverage)
  bit opcodes[128], csrs[4096], exceptions[2], interrupts[2];
  int unsigned samples;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void write(cpu_retirement t);
   bit [31:0] insn=32'(t.values[2]);
   opcodes[insn[6:0]]=1;
   if(insn[6:0]==7'h73 && insn[14:12]!=0) csrs[insn[31:20]]=1;
   exceptions[t.values[11]!=0]=1; interrupts[t.values[17]!=0]=1; samples++;
  endfunction
 endclass
 // Protocol agents call access after accepting a request. Both ports share it.
 class cpu_memory extends uvm_object;
  `uvm_object_utils(cpu_memory)
  byte unsigned bytes[longint unsigned];
  longint unsigned base, size;
  int unsigned max_wait=3;
  bit fetch_fault_enable;
  longint unsigned fetch_fault_address;
  function new(string name="cpu_memory"); super.new(name); endfunction
  function void preload(string path);
   int fd, rc; longint unsigned address, value;
   fd=$fopen(path,"r"); if(!fd) `uvm_fatal("ELF_IMAGE","cannot open byte image")
   while(!$feof(fd)) begin
    rc=$fscanf(fd,"%h %h",address,value);
    if(rc==2) begin
     if(address<base || address-base>=size || value>255) `uvm_fatal("ELF_IMAGE","image outside RAM")
     bytes[address]=8'(value);
    end else if(!$feof(fd)) `uvm_fatal("ELF_IMAGE","invalid byte image")
   end
   $fclose(fd);
  endfunction
  task access(virtual rvw_cpu_if vif, bit instruction, bit write,
              longint unsigned address, bit [31:0] wdata, bit [3:0] mask,
              output bit [31:0] rdata, output bit error);
   int delay_cycles=$urandom_range(max_wait,0);
   repeat(delay_cycles) @(posedge vif.clk);
   rdata=0; error=(address<base || size<4 || address-base>size-4 || address%4!=0);
   error|=instruction && fetch_fault_enable && address==fetch_fault_address;
   if(!error) for(int i=0;i<4;i++) begin
    if(write && mask[i]) bytes[address+i]=wdata[i*8+:8];
    if(bytes.exists(address+i)) rdata[i*8+:8]=bytes[address+i];
   end
  endtask
 endclass
 class cpu_control_sequence extends uvm_sequence;
  `uvm_object_utils(cpu_control_sequence)
  virtual rvw_cpu_if vif;
  function new(string name="cpu_control_sequence"); super.new(name); endfunction
  task reset(int cycles=5);
   vif.reset_n=0; vif.irq=0; vif.debug_req=0;
   repeat(cycles) @(negedge vif.clk);
   vif.reset_n=1;
  endtask
  task interrupt_pulse(int unsigned mask, int cycles=1);
   @(negedge vif.clk); vif.irq=mask;
   repeat(cycles) @(negedge vif.clk); vif.irq=0;
  endtask
  task debug_pulse(int cycles=1);
   @(negedge vif.clk); vif.debug_req=1;
   repeat(cycles) @(negedge vif.clk); vif.debug_req=0;
  endtask
  task random_requests(int count, bit [31:0] allowed_irqs, int max_gap=8);
   if(count<1 || max_gap<1 || allowed_irqs==0)
    `uvm_fatal("CONTROL_CONFIG","positive count/gap and project IRQ mask required")
   repeat(count) begin
    bit [31:0] levels=$urandom & allowed_irqs;
    repeat($urandom_range(max_gap,1)) @(negedge vif.clk);
    if($urandom_range(1,0)) debug_pulse($urandom_range(3,1));
    else interrupt_pulse(levels==0 ? allowed_irqs & (~allowed_irqs+1) : levels,$urandom_range(3,1));
   end
  endtask
 endclass
 class cpu_virtual_sequencer extends uvm_sequencer;
  `uvm_component_utils(cpu_virtual_sequencer)
  cpu_control_sequence controls;
  cpu_memory memory;
  cpu_scoreboard scoreboard;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
 endclass
 class cpu_program_sequence extends uvm_sequence;
  `uvm_object_utils(cpu_program_sequence)
  `uvm_declare_p_sequencer(cpu_virtual_sequencer)
  string byte_image;
  int unsigned retirements, max_cycles=1000;
  function new(string name="cpu_program_sequence"); super.new(name); endfunction
  task body();
   bit complete=0;
   if(retirements==0 || max_cycles==0) `uvm_fatal("PROGRAM_CONFIG","positive retirement and cycle bounds required")
   p_sequencer.memory.preload(byte_image);
   p_sequencer.controls.reset();
   repeat(max_cycles) begin
    @(negedge p_sequencer.controls.vif.clk);
    if(p_sequencer.scoreboard.checks==retirements) begin complete=1; break; end
   end
   if(!complete) `uvm_fatal("CPU_WATCHDOG","program did not reach its expected retirement count")
  endtask
 endclass
 class cpu_random_control_sequence extends uvm_sequence;
  `uvm_object_utils(cpu_random_control_sequence)
  `uvm_declare_p_sequencer(cpu_virtual_sequencer)
  bit [31:0] allowed_irqs;
  int count=16, max_gap=8;
  function new(string name="cpu_random_control_sequence"); super.new(name); endfunction
  task body(); p_sequencer.controls.random_requests(count,allowed_irqs,max_gap); endtask
 endclass
 class cpu_env extends uvm_env;
  `uvm_component_utils(cpu_env)
  cpu_monitor monitor;
  cpu_scoreboard scoreboard;
  cpu_coverage coverage;
  cpu_memory memory;
  cpu_virtual_sequencer vseqr;
  function new(string name,uvm_component parent); super.new(name,parent); endfunction
  function void build_phase(uvm_phase phase);
   if(!uvm_config_db#(cpu_memory)::get(this,"","memory",memory))
    memory=cpu_memory::type_id::create("memory");
   vseqr=cpu_virtual_sequencer::type_id::create("vseqr",this);
   vseqr.controls=new("controls");
   monitor=cpu_monitor::type_id::create("monitor",this);
   scoreboard=cpu_scoreboard::type_id::create("scoreboard",this);
   coverage=cpu_coverage::type_id::create("coverage",this);
  endfunction
  function void connect_phase(uvm_phase phase);
   vseqr.memory=memory; vseqr.scoreboard=scoreboard; vseqr.controls.vif=monitor.vif;
   monitor.ap.connect(scoreboard.analysis_export); monitor.ap.connect(coverage.analysis_export);
  endfunction
 endclass
endpackage
