"""Capture pinned PicoRV32 and add architectural snapshots, not RVFI aliases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PIN = 'ef203c2b0a3fb793280f5114941416c425c5b461'


def prepare(source, out, formal_root):
    source, out = Path(source).resolve(), Path(out).resolve()
    revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip()
    if revision != PIN:
        raise ValueError('PicoRV32 revision does not match the pinned source')
    raw = (source/'picorv32.v').read_text()
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain','--','picorv32.v'],text=True):
        raise ValueError('PicoRV32 source is modified')
    out.mkdir(parents=True,exist_ok=False)
    # Simulation and formal compare this simple RV32I configuration.
    raw = raw.replace('parameter [ 0:0] ENABLE_COUNTERS = 1', 'parameter [ 0:0] ENABLE_COUNTERS = 0')
    raw = raw.replace('parameter [ 0:0] REGS_INIT_ZERO = 0', 'parameter [ 0:0] REGS_INIT_ZERO = 1')
    snapshot = '''
wire state_reset = !resetn;
reg state_retire = 0;
reg [31:0] state_insn, state_pc_before, state_pc_after;
reg state_trap;
wire state_halt = state_trap;
wire state_intr = 0;
wire [1:0] state_mode = 3;
reg [4:0] state_rs1, state_rs2, state_rd;
reg [1023:0] state_regs_before, state_regs_after;
reg [1023:0] instruction_before;
reg [4:0] pending_rd;
reg [31:0] memory_addr, memory_rdata, memory_wdata;
reg [3:0] memory_rmask, memory_wmask;
reg [31:0] state_mem_addr, state_mem_rdata, state_mem_wdata;
reg [3:0] state_mem_rmask, state_mem_wmask;
wire retire_event = resetn && (launch_next_insn || trap) && dbg_valid_insn;
reg [1023:0] effective_regs;
integer snapshot_i;
always @* begin
    effective_regs = 0;
    for(snapshot_i=1; snapshot_i<32; snapshot_i=snapshot_i+1)
        effective_regs[snapshot_i*32 +: 32] = cpuregs[snapshot_i];
    if(resetn && cpuregs_write && latched_rd != 0)
        effective_regs[latched_rd*32 +: 32] = cpuregs_wrdata;
end
always @(posedge clk) begin
    state_retire <= retire_event;
    if(!resetn) begin
        pending_rd <= 0;
        instruction_before <= 0;
        memory_addr <= 0; memory_rdata <= 0; memory_wdata <= 0;
        memory_rmask <= 0; memory_wmask <= 0;
    end else begin
        if(cpuregs_write) pending_rd <= latched_rd;
        if(launch_next_insn) begin
            instruction_before <= effective_regs;
            pending_rd <= 0;
        end
        if(mem_instr) begin
            memory_addr <= 0; memory_rdata <= 0; memory_wdata <= 0;
            memory_rmask <= 0; memory_wmask <= 0;
        end else if(mem_valid && mem_ready) begin
            memory_addr <= mem_addr; memory_rdata <= mem_rdata; memory_wdata <= mem_wdata;
            memory_rmask <= mem_wstrb ? 0 : 15;
            memory_wmask <= mem_wstrb;
        end
    end
    if(retire_event) begin
        state_insn <= dbg_insn_opcode;
        state_pc_before <= dbg_insn_addr;
        state_pc_after <= launch_next_insn ? next_pc : dbg_insn_addr;
        state_trap <= trap;
        state_rs1 <= dbg_rs1val_valid ? dbg_insn_rs1 : 0;
        state_rs2 <= dbg_rs2val_valid ? dbg_insn_rs2 : 0;
        state_rd <= trap ? 0 : cpuregs_write ? latched_rd : pending_rd;
        state_regs_before <= instruction_before;
        state_regs_after <= effective_regs;
        state_mem_addr <= memory_addr; state_mem_rdata <= memory_rdata;
        state_mem_wdata <= memory_wdata; state_mem_rmask <= memory_rmask;
        state_mem_wmask <= memory_wmask;
    end
end
'''
    # Insert only in the base core, before its first endmodule.
    raw = '`define RISCV_FORMAL\n' + raw.replace('endmodule', snapshot+'\nendmodule',1)
    (out/'picorv32-observed.sv').write_text(raw)
    signals={k:'state_'+k for k in ('retire','insn','pc_before','pc_after','regs_before','regs_after','rs1','rs2','rd','trap','halt','intr','mode','mem_addr','mem_rmask','mem_wmask','mem_rdata','mem_wdata')}
    plan=dict(schema='rvw.architectural-state/1', name='picorv32-state', xlen=32, top='picorv32',clock='clk',reset='resetn',reset_active_low=True,
              verilog=['picorv32-observed.sv'], signals=signals,
              riscv_formal=dict(root=str(Path(formal_root).resolve()),isa='rv32i',nret=1,checks=['insn_add_ch0','cover'],depth=30,solver='bitwuzla'))
    (out/'state-map.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'source.json').write_text(json.dumps(dict(revision=revision,sha256=hashlib.sha256((source/'picorv32.v').read_bytes()).hexdigest(),
         limits=['RV32I, no compressed instructions, IRQ or PCPI.', 'Snapshots use architectural register storage and retirement events.',
                 'Source values are read from the pre-instruction register snapshot.', 'Memory effects retain bus data and masks.']),indent=2)+'\n')
    return plan


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--riscv-formal',required=True)
    a=p.parse_args();prepare(a.source,a.out,a.riscv_formal)
