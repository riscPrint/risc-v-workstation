"""Compare the state monitor and native RVFI through each pinned RV32UI test."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from prepare import prepare
from rvw.common.proc import run_group

M_TESTS = {'mul','mulh','mulhsu','mulhu','div','divu','rem','remu'}


def suite_sources(source, tests=None):
    directory=Path(tests) if tests else Path(source)/'tests'
    return sorted(p for p in directory.glob('*.S') if p.stem not in M_TESTS)


def relocate_hex(text):
    def address(match):
        value = int(match[1],16)-0x20000000
        if not 0 <= value < 262144:
            raise ValueError('program address is outside the one-MiB test RAM')
        return '@'+format(value,'08x')
    return re.sub(r'@([0-9a-fA-F]+)',address,text)


def overall(rows):
    return 'failed' if any(r['status']=='failed' for r in rows) else 'matched' if rows and all(r['status']=='matched' for r in rows) else 'inconclusive'


def run(source, formal_root, out, prefix, tests=None):
    source=Path(source).resolve();out=Path(out).resolve()
    prepare(source,out,formal_root)
    helper=Path(__file__).resolve().parent
    def execute(argv, name, timeout=90):
        result=run_group(argv,cwd=out,timeout=timeout,capture=True)
        (out/(name+'.log')).write_text((result.stdout or '')+(result.stderr or ''))
        return result
    result=execute([sys.executable,str(helper/'compare.py'),'--capture',str(out)],'prepare-comparison')
    if result.returncode or result.timed_out: raise ValueError('comparison generation failed')
    tb='''module tb;
reg clk=0; always #5 clk=~clk;
reg resetn=0; initial begin repeat(3) @(negedge clk); resetn=1; end
reg [31:0] ram[0:262143]; integer i; integer count=0;
reg [31:0] tohost; reg completed=0; reg [1023:0] program_file;
wire mem_valid,mem_instr; wire [31:0] mem_addr,mem_wdata; wire [3:0] mem_wstrb;
wire [31:0] mem_rdata=ram[mem_addr[19:2]];
initial begin
 if(!$value$plusargs("hex=%s",program_file)) $fatal(1,"missing hex");
 if(!$value$plusargs("tohost=%h",tohost)) $fatal(1,"missing tohost");
 for(i=0;i<262144;i=i+1) ram[i]=0;
 $readmemh(program_file,ram);
 #10000000; $fatal(1,"test timeout");
end
always @(posedge clk) if(resetn) begin
 if(dut.rvfi_valid) count=count+1;
 if(completed && dut.rvfi_valid && |dut.rvfi_mem_wmask && dut.rvfi_mem_addr==tohost) begin
  #1; $display("MATCH retirements=%0d",count); $finish;
 end
 if(mem_valid && |mem_wstrb) begin
  for(i=0;i<4;i=i+1) if(mem_wstrb[i]) ram[mem_addr[19:2]][i*8+:8]<=mem_wdata[i*8+:8];
  if(mem_addr==tohost) begin
   if(mem_wdata!=1) $fatal(1,"ISA test failed: %h",mem_wdata);
   completed<=1;
  end
 end
end
picorv32 #(.PROGADDR_RESET(32'h80000000)) dut(.clk(clk),.resetn(resetn),.mem_valid(mem_valid),.mem_instr(mem_instr),.mem_ready(1'b1),.mem_addr(mem_addr),.mem_wdata(mem_wdata),.mem_wstrb(mem_wstrb),.mem_rdata(mem_rdata),.pcpi_wr(1'b0),.pcpi_rd(32'b0),.pcpi_wait(1'b0),.pcpi_ready(1'b0),.irq(32'b0));
endmodule
'''
    (out/'suite_tb.sv').write_text(tb)
    result=execute(['iverilog','-g2012','-s','tb','-o','suite-sim','miter.sv','monitor.sv','suite_tb.sv'],'compile')
    if result.returncode or result.timed_out: raise ValueError('suite compilation failed')
    rows=[]
    for program in suite_sources(source,tests):
        name=program.stem
        elf=out/(name+'.elf')
        result=execute([prefix+'gcc','-march=rv32im_zifencei','-mabi=ilp32','-nostdlib','-nostartfiles','-include',str(helper.parent/'rvw/env/riscv_test.h'),'-I'+str(helper.parent/'rvw/env'),'-I'+str(program.parent),'-I'+str(program.parent.parent/'macros/scalar'),'-T',str(helper.parent/'rvw/programs/link.ld'),'-Wl,--build-id=none',str(program),'-o',str(elf)],name+'-build')
        row=dict(test='rv32ui-'+name,source_sha256=hashlib.sha256(program.read_bytes()).hexdigest())
        rows.append(row)
        if result.returncode or result.timed_out:
            row.update(status='inconclusive',reason='test build failed');continue
        row['elf_sha256']=hashlib.sha256(elf.read_bytes()).hexdigest()
        result=execute([prefix+'nm',str(elf)],name+'-symbols')
        symbols=result.stdout or ''
        match=re.search(r'^([0-9a-fA-F]+)\s+\w\s+tohost$',symbols,re.M)
        if not match: row.update(status='inconclusive',reason='missing tohost');continue
        result=execute([prefix+'objcopy','-O','verilog','--verilog-data-width=4',str(elf),name+'.hex'],name+'-hex')
        if result.returncode: row.update(status='inconclusive',reason='hex export failed');continue
        hexfile=out/(name+'.hex');hexfile.write_text(relocate_hex(hexfile.read_text()))
        result=execute(['vvp','suite-sim','+hex='+name+'.hex','+tohost='+match[1]],name+'-simulation')
        text=(result.stdout or '')+(result.stderr or '')
        observed=re.search(r'MATCH retirements=(\d+)',text)
        row.update(status='matched' if result.returncode==0 and observed and not result.timed_out else 'inconclusive' if result.timed_out or 'test timeout' in text else 'failed',reason='cycle or wall limit' if result.timed_out or 'test timeout' in text else '',retirements=int(observed[1]) if observed else None,log=name+'-simulation.log')
    report=dict(schema='rvw.pico-state-suite/1',core_source=json.loads((out/'source.json').read_text()),rows=rows,status=overall(rows),test_selection='external rv32ui' if tests else 'PicoRV32 bundled RV32UI',limits=['RV32M tests are excluded.','Finite simulation comparison of all base RVFI fields; not formal equivalence.','Trap-write negative control and full bounded equivalence remain failed.'])
    (out/'suite-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','riscv-formal','out'):p.add_argument('--'+name,required=True)
    p.add_argument('--prefix',default='riscv64-unknown-elf-')
    p.add_argument('--tests',help='full upstream isa/rv32ui directory; default uses PicoRV32 bundled tests')
    a=p.parse_args();report=run(a.source,a.riscv_formal,a.out,a.prefix,a.tests)
    raise SystemExit({'matched':0,'failed':1,'inconclusive':3}[report['status']])
