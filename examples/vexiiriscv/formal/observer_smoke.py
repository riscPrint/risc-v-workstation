"""Check directed retirement, memory and trap alignment on exported VexiiRiscv RTL."""
import argparse
import hashlib
import json
from pathlib import Path
from rvw.common.proc import run_group


def bench():
    b=json.loads(Path(__file__).with_name('binding.json').read_text())
    widths={**b['inputs'],**b['outputs'],**{'rvfi_'+k:v for k,v in __import__('rvw.formal.architectural_state',fromlist=['monitor']).monitor(32)[2].items()}}
    f='FetchCachelessPlugin_logic_bus_';d='LsuCachelessPlugin_logic_bus_'
    lines=['module tb; reg clk=0; always #5 clk=~clk; reg reset=1;', 'initial begin repeat(5) @(negedge clk); reset=0; end']
    for n,w in widths.items():
     typ='reg' if n in b['inputs'] else 'wire'
     lines.append(f'{typ} [{w-1}:0] {n};')
    lines+=['reg [31:0] ram[0:511]; integer i; integer cycles=0; integer seen=0; reg saw_load=0,saw_store=0,saw_trap=0,saw_handler=0,saw_return=0;','initial begin for(i=0;i<512;i=i+1) ram[i]=32\'h00000013;']
    program={0:0x800000b7,4:0x10008093,8:0x00700113,12:0x0020a023,16:0x0000a183,20:0x00218233,24:0x00000297,28:0x02828293,32:0x30529073,36:0x00000073,40:0x00100313,44:0x0000006f,64:0x341023f3,68:0x00438393,72:0x34139073,76:0x30200073}
    for pc,insn in program.items(): lines.append(f"ram[{pc//4}]=32'h{insn:08x};")
    for n,w in b['inputs'].items(): lines.append(f'{n}=0;')
    lines+= [f'{f}cmd_ready=1; {d}cmd_ready=1; end',
     f'''always @(posedge clk) begin
    {f}rsp_valid <= !reset && {f}cmd_valid;
    {f}rsp_payload_id <= {f}cmd_payload_id;
    {f}rsp_payload_word <= ram[{f}cmd_payload_address[10:2]];
    {d}rsp_valid <= !reset && {d}cmd_valid;
    {d}rsp_payload_id <= {d}cmd_payload_id;
    {d}rsp_payload_data <= ram[{d}cmd_payload_address[10:2]];
    if(!reset && {d}cmd_valid && {d}cmd_payload_write) begin
    for(i=0;i<4;i=i+1) if({d}cmd_payload_mask[i]) ram[{d}cmd_payload_address[10:2]][i*8+:8] <= {d}cmd_payload_data[i*8+:8];
    end
    cycles<=cycles+1;
    if(cycles>3000) $fatal(1,"observer timeout");
    if(!reset && rvfi_valid) begin
    $display("RVFI %0d pc=%h next=%h insn=%h rd=%0d data=%h trap=%b intr=%b mem=%h rmask=%h wmask=%h rdata=%h wdata=%h",rvfi_order,rvfi_pc_rdata,rvfi_pc_wdata,rvfi_insn,rvfi_rd_addr,rvfi_rd_wdata,rvfi_trap,rvfi_intr,rvfi_mem_addr,rvfi_mem_rmask,rvfi_mem_wmask,rvfi_mem_rdata,rvfi_mem_wdata);
    if(seen>=15 || rvfi_order !== seen) $fatal(1,"order mismatch");
if(rvfi_pc_rdata !== expected_pc[seen] || rvfi_pc_wdata !== expected_next[seen] || rvfi_insn !== ram[expected_pc[seen][10:2]]) $fatal(1,"instruction or PC mismatch");
if(rvfi_rd_addr !== expected_rd[seen] || rvfi_rd_wdata !== expected_data[seen]) $fatal(1,"destination mismatch");
if(rvfi_rs1_addr !== expected_rs1[seen] || rvfi_rs1_rdata !== expected_a[seen] || rvfi_rs2_addr !== expected_rs2[seen] || rvfi_rs2_rdata !== expected_b[seen]) $fatal(1,"source mismatch");
if(rvfi_trap !== (seen==9) || rvfi_intr !== (seen==10) || rvfi_mode !== 2'b11 || rvfi_ixl !== 2'b01 || rvfi_halt !== 0) $fatal(1,"control mismatch");
if(seen!=3 && seen!=4 && (rvfi_mem_addr !== 0 || rvfi_mem_rmask !== 0 || rvfi_mem_wmask !== 0 || rvfi_mem_rdata !== 0 || rvfi_mem_wdata !== 0)) $fatal(1,"unexpected memory effect");
if(seen==3 && (rvfi_mem_rmask !== 0 || rvfi_mem_rdata !== 0)) $fatal(1,"store read effect mismatch");
if(seen==4 && (rvfi_mem_wmask !== 0 || rvfi_mem_wdata !== 0)) $fatal(1,"load write effect mismatch");
seen=seen+1;
    case(rvfi_pc_rdata)
    32'h8000000c: begin
    if(rvfi_mem_addr !== 32'h80000100 || rvfi_mem_wmask !== 4'hf || rvfi_mem_wdata !== 7) $fatal(1,"store mismatch"); saw_store=1;
    end
    32'h80000010: begin
    if(rvfi_mem_addr !== 32'h80000100 || rvfi_mem_rmask !== 4'hf || rvfi_mem_rdata !== 7 || rvfi_rd_wdata !== 7) $fatal(1,"load mismatch"); saw_load=1;
    end
    32'h80000014: if(rvfi_rd_wdata !== 14) $fatal(1,"dependent result mismatch");
    32'h80000020: if(rvfi_pc_wdata !== 32'h80000024) $fatal(1,"pretrap next PC mismatch");
    32'h80000024: begin
    if(rvfi_insn !== 32'h00000073 || rvfi_trap !== 1 || rvfi_rd_addr !== 0 || rvfi_pc_wdata !== 32'h80000040) $fatal(1,"trap mismatch"); saw_trap=1;
    end
    32'h80000040: begin if(rvfi_intr !== 1) $fatal(1,"handler boundary mismatch"); saw_handler=1; end
    32'h8000004c: begin if(rvfi_pc_wdata !== 32'h80000028) $fatal(1,"return mismatch"); saw_return=1; end
    32'h80000028: begin
    if(rvfi_rd_wdata !== 1 || !(saw_load && saw_store && saw_trap && saw_handler && saw_return)) $fatal(1,"missing observations");
    $display("OBSERVER_SMOKE_PASS records=%0d",seen); $finish;
    end
    endcase
    end
    end''']
    # Expected architectural records for the fixed program, including ECALL.
    pcs=[0,4,8,12,16,20,24,28,32,36,64,68,72,76,40]
    destinations=[1,1,2,0,3,4,5,5,0,0,7,7,0,0,6]
    values=[0x80000000,0x80000100,7,0,7,14,0x80000018,0x80000040,0,0,0x80000024,0x80000028,0,0,1]
    source1=[0,1,0,1,1,3,0,5,5,0,0,7,7,0,0]
    source1_data=[0,0x80000000,0,0x80000100,0x80000100,7,0,0x80000018,0x80000040,0,0,0x80000024,0x80000028,0,0]
    source2=[0,0,0,2,0,2,0,0,0,0,0,0,0,0,0]
    source2_data=[0,0,0,7,0,7,0,0,0,0,0,0,0,0,0]
    arrays=dict(expected_pc=[0x80000000+x for x in pcs],expected_next=[0x80000000+x for x in pcs[1:]+[44]],
                expected_rd=destinations,expected_data=values,expected_rs1=source1,expected_a=source1_data,
                expected_rs2=source2,expected_b=source2_data)
    expected_lines=[]
    for name,items in arrays.items():
        expected_lines.append(f"reg [31:0] {name}[0:14]; initial begin")
        expected_lines.extend(f"{name}[{i}]=32'h{value:08x};" for i,value in enumerate(items))
        expected_lines.append('end')
    lines[1:1]=expected_lines
    lines+=['VexiiRiscv dut(.clk(clk),.reset(reset),'+','.join(f'.{n}({n})' for n in widths)+');','endmodule']
    return '\n'.join(lines)+'\n'


def verdict(code, text, *, negative=False):
    if negative:
        return 'detected' if code != 0 and 'store mismatch' in text else 'inconclusive'
    if 'FAILURE' in text or 'FATAL' in text:
        return 'failed'
    if code == 0 and 'OBSERVER_SMOKE_PASS records=' in text:
        return 'matched'
    return 'failed' if code != 0 and ('mismatch' in text or 'FAILURE' in text or 'FATAL' in text) else 'inconclusive'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtl',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    raw=Path(a.rtl).read_bytes();(out/'core.v').write_bytes(raw)
    text=bench();rows=[]
    for negative in (False,True):
        name='negative' if negative else 'positive'
        body=text.replace('module tb;',"module tb; initial force dut.rvfi_mem_wdata=32'b0;",1) if negative else text
        (out/(name+'.sv')).write_text(body)
        with (out/(name+'-compile.log')).open('w') as log:
            built=run_group(['iverilog','-g2012','-s','tb','-o',name,'core.v',name+'.sv'],cwd=out,stdout=log,stderr=log,timeout=30)
        if built.returncode or built.timed_out:
            rows.append(dict(case=name,status='inconclusive',reason='compile failed or timed out'));continue
        proc=run_group(['vvp',name],cwd=out,capture=True,timeout=30)
        output=(proc.stdout or '')+(proc.stderr or '')
        (out/(name+'.log')).write_text(output)
        rows.append(dict(case=name,status='inconclusive' if proc.timed_out else verdict(proc.returncode,output,negative=negative),
                         returncode=proc.returncode,timed_out=proc.timed_out))
    report=dict(schema='rvw.vexii-observer-smoke/1',rtl_sha256=hashlib.sha256(raw).hexdigest(),
                bench_sha256=hashlib.sha256(text.encode()).hexdigest(),rows=rows,
                status='matched' if [r['status'] for r in rows]==['matched','detected'] else 'failed' if any(r['status']=='failed' for r in rows) else 'inconclusive',
                limits=['One directed program, not formal observer equivalence.',
                        'Normal retirements, dependent load/store, ECALL, handler boundary and MRET.',
                        'Negative control forces only the observer store-data output to zero.',
                        'Interrupts, I/O and overlapping fault/commit events remain unqualified.'])
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['status']=='matched' else 1


if __name__=='__main__':raise SystemExit(main())
