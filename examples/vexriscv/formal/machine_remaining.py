"""Prepare RV32IM CSR, fetch, kill-history and trap-PC checks."""
import argparse
import hashlib
import json
from pathlib import Path
from machine_m import RTL_SHA256


def prepare(rtl, out, depth=25):
    if type(depth) is not int or not 2 <= depth <= 200:
        raise ValueError("depth must be 2..200")
    raw = Path(rtl).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RTL_SHA256:
        raise ValueError('select the measured FormalMTop RTL')
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    # Independent ordered bus-response PC tracker. The environment supplies
    # ordered responses, with at least one cycle of latency, without errors.
    text = '''
reg [31:0] audit_fetch_pc [0:7];
reg [2:0] audit_head=0, audit_tail=0;
reg [3:0] audit_count=0;
wire audit_cmd = iBus_cmd_valid && iBus_cmd_ready;
wire audit_rsp = iBus_rsp_valid;
wire [31:0] audit_rsp_pc = audit_fetch_pc[audit_head];
always @(posedge clk) if(reset) begin
 audit_head<=0; audit_tail<=0; audit_count<=0;
end else begin
 assume(!iBus_rsp_payload_error);
 assume(!audit_rsp || audit_count != 0);
 assert(!audit_cmd || audit_count < 8 || audit_rsp);
 if(audit_cmd) begin audit_fetch_pc[audit_tail]<=iBus_cmd_payload_pc; audit_tail<=audit_tail+1; end
 if(audit_rsp) audit_head<=audit_head+1;
 case({audit_cmd,audit_rsp})
 2'b10: audit_count<=audit_count+1;
 2'b01: audit_count<=audit_count-1;
 endcase
end
wire audit_retire = rvfi_valid && !rvfi_trap && !rvfi_halt;
wire audit_fetch = !reset && audit_rsp;
wire [31:0] audit_pc = rvfi_pc_rdata;
wire [31:0] audit_insn = rvfi_insn;
wire [31:0] audit_data = iBus_rsp_payload_inst;
// Track the fetched instruction through all four stage boundaries.
reg audit_execute_live=0, audit_memory_live=0, audit_writeback_live=0;
always @(posedge clk) if(reset) begin
 audit_execute_live<=0; audit_memory_live<=0; audit_writeback_live<=0;
end else begin
 if(!execute_arbitration_isStuck || execute_arbitration_removeIt)
   audit_execute_live <= decode_arbitration_isFiring;
 if(!memory_arbitration_isStuck || memory_arbitration_removeIt)
   audit_memory_live <= execute_arbitration_isFiring && audit_execute_live;
 if(!writeBack_arbitration_isStuck || writeBack_arbitration_removeIt)
   audit_writeback_live <= memory_arbitration_isFiring && audit_memory_live;
end
wire audit_retired_killed = !audit_writeback_live || writeBack_arbitration_removeIt;
reg audit_redirect=0;
reg [31:0] audit_redirect_pc;
always @(posedge clk) if(reset) audit_redirect<=0; else begin
 if(audit_retire) audit_redirect<=0;
 if(CsrPlugin_jumpInterface_valid) begin
  audit_redirect<=1; audit_redirect_pc<=CsrPlugin_jumpInterface_payload;
 end
end
reg audit_csr_event;
reg [11:0] audit_csr_address;
reg [2:0] audit_csr_op;
reg [31:0] audit_csr_operand,audit_csr_before,audit_csr_read;
reg audit_csr_trap;
reg [1:0] audit_csr_mode;
wire [31:0] audit_csr_after=CsrPlugin_mscratch;
always @(posedge clk) begin
 audit_csr_event<=!reset && execute_CsrPlugin_readEnable && execute_CsrPlugin_csrAddress==12'h340;
 audit_csr_address<=execute_CsrPlugin_csrAddress;
 audit_csr_op<={1'b0,execute_INSTRUCTION[13:12]};
 audit_csr_operand<=execute_SRC1;
 audit_csr_before<=CsrPlugin_mscratch;
 audit_csr_read<=CsrPlugin_csrMapping_readDataSignal;
 audit_csr_trap<=execute_CsrPlugin_illegalAccess;
 audit_csr_mode<=CsrPlugin_privilege;
end
'''
    checks = {
        'csr_consistency':dict(csr='mscratch',write_mask=0xffffffff,signals=dict(event='audit_csr_event',address='audit_csr_address',op='audit_csr_op',operand='audit_csr_operand',before='audit_csr_before',after='audit_csr_after',read_data='audit_csr_read',trap='audit_csr_trap',mode='audit_csr_mode')),
        'instruction_memory':dict(signals=dict(retire='audit_retire',pc='audit_pc',insn='audit_insn',fetch='audit_fetch',fetch_addr='audit_rsp_pc',fetch_data='audit_data')),
        'flush_retirement':dict(signals=dict(retire='audit_retire',retired_killed='audit_retired_killed')),
        'trap_pc_chain':dict(signals=dict(retire='audit_retire',pc='audit_pc',next_pc='rvfi_pc_wdata',redirect='audit_redirect',redirect_pc='audit_redirect_pc')),
    }
    for selection in checks.values(): selection['engine']='smtbmc bitwuzla'
    (out/'observed.v').write_text(raw.decode().replace('endmodule',text+'\nendmodule',1))
    plan=dict(schema='rvw.machine-checks/1',xlen=32,top='VexRiscv',clock='clk',reset='reset',sources=['observed.v'],depth=depth,checks=checks)
    (out/'machine.json').write_text(json.dumps(plan,indent=2)+'\n')
    return plan

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtl',required=True);p.add_argument('--out',required=True)
    p.add_argument('--depth',type=int,default=25)
    a=p.parse_args();prepare(a.rtl,a.out,a.depth)
