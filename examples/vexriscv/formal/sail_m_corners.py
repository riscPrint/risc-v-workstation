"""Check generated M arithmetic with independent integer corner values."""
import argparse
import json
from pathlib import Path
from rvw.common.proc import run_group


def main():
    p=argparse.ArgumentParser();p.add_argument('--models',required=True);args=p.parse_args()
    root=Path(args.models).resolve();meta=json.loads((root/'manifest.json').read_text())
    lines=['module tb; reg [31:0] a,b;']
    for name in meta['files']:
        port=meta['files'][name]['generated_result']
        lines += [f'wire [31:0] {name}; sail_{name} dut_{name}(.a_0(a),.b_0(b),.{port}({name}));']
    lines+=['initial begin']
    values=[0,1,0xffffffff,0x80000000,0x7fffffff,2,0xfffffffe]
    def signed(x): return x if x<2**31 else x-2**32
    for a in values:
        for b in values:
            sa,sb=signed(a),signed(b)
            q=((-1 if (sa<0)!=(sb<0) else 1)*(abs(sa)//abs(sb))) if sb else -1
            expected=dict(mul=a*b,mulh=(sa*sb)>>32,mulhsu=(sa*b)>>32,mulhu=(a*b)>>32,
                          div=q,divu=a//b if b else -1,rem=sa-q*sb if sb else sa,remu=a%b if b else a)
            lines += [f"a=32'h{a:08x}; b=32'h{b:08x}; #1;"]
            for name,result in expected.items():
                lines += [f"if({name} !== 32'h{result&0xffffffff:08x}) $fatal(1,\"{name} a={a:08x} b={b:08x}\");"]
    lines+=['$display("392 arithmetic corner comparisons passed"); $finish; end endmodule']
    (root/'corners.sv').write_text('\n'.join(lines))
    with (root/'corners.log').open('w') as log:
        r=run_group(['iverilog','-g2012','-D','RISCV_FORMAL_XLEN=32','-D','RISCV_FORMAL_ILEN=32','-s','tb','-o','corners',
                     *[f'insn_{n}.v' for n in meta['files']],'corners.sv'],cwd=root,stdout=log,stderr=log,timeout=30)
        if not r.returncode and not r.timed_out:
            r=run_group(['vvp','corners'],cwd=root,stdout=log,stderr=log,timeout=30)
    if r.returncode or r.timed_out or '392 arithmetic corner comparisons passed' not in (root/'corners.log').read_text():
        raise SystemExit('M arithmetic comparison failed; see corners.log')
    print('392 arithmetic corner comparisons passed')


if __name__=='__main__':main()
