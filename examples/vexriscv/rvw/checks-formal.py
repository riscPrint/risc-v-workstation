#!/usr/bin/env python3
"""Prepare bounded obligations on captured VexRiscv command ports."""
import argparse
from pathlib import Path
import re


def prepare(rtl, generated, out):
    rtl,generated,out=map(Path,(rtl,generated,out))
    out.mkdir(parents=True,exist_ok=False)
    monitors=(generated/'streams/monitors.sv').read_text()
    binds=(generated/'streams/binds.sv').read_text().splitlines()
    manifest=['core = "vexriscv"','config = "rv32im-generated-port-checks"']
    for name in ('iBus_cmd','dBus_cmd'):
        binding=next(line for line in binds if f'.{name}_valid(' in line)
        module=binding.split()[2]
        match=re.search(r'module '+module+r'\(.*?\nendmodule',monitors,re.S)
        if not match: raise ValueError('expected captured command channel '+module)
        text=match[0]
        asserts=list(re.finditer(r'^\s*assert \(.*?;\s*$',text,re.M))
        if len(asserts)<2: raise ValueError('expected valid-hold and payload-stability assertions')
        instance=binding.removeprefix('bind VexTop ')
        for n in range(len(asserts)):
            kind='stream.valid_hold' if n==0 else 'stream.payload_stable'
            key=name+'_'+str(n)
            directory=out/key;directory.mkdir()
            checker=text
            for omitted in reversed([a for j,a in enumerate(asserts) if j!=n]):
                checker=checker[:omitted.start()]+'\n// Other property checked separately.\n'+checker[omitted.end():]
            (directory/'monitor.sv').write_text(checker+'\n')
            found=False
            for src in sorted(rtl.glob('*.v')):
                original=src.read_text()
                top=re.search(r'\bmodule\s+VexTop\b',original)
                if top:
                    end=original.index('endmodule',top.end())
                    reset='''
reg [1:0] rvw_reset_age = 0;
always @(posedge clk) if (rvw_reset_age != 3) rvw_reset_age <= rvw_reset_age + 1'b1;
always @* assume(reset == (rvw_reset_age < 2));
'''
                    original=original[:end]+reset+instance+'\n'+original[end:]
                    found=True
                (directory/src.name).write_text(original)
            if not found: raise ValueError('VexTop RTL missing')
            files=' '.join(p.name for p in sorted(directory.glob('*.v')))
            (directory/'job.sby').write_text('[options]\nmode bmc\ndepth 6\n\n[engines]\nsmtbmc yices\n\n[script]\n'
                +'read_verilog -formal '+files+'\nchformal -assert -remove\n'
                +'read_verilog -formal monitor.sv\nprep -top VexTop\nasync2sync\ndffunmap\n\n[files]\n'
                +'\n'.join(p.name for p in sorted(directory.glob('*.v')))+'\nmonitor.sv\n')
            manifest+=['','[[property]]',f'id = "{key}"',f'sby = "{key}/job.sby"','top = "VexTop"',
                f'requirements = ["{kind}:{name}"]','assumptions = ["reset asserted for first two clocks; other inputs arbitrary"]']
    (out/'regress.toml').write_text('\n'.join(manifest)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--rtl',required=True)
    p.add_argument('--generated',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    prepare(a.rtl,a.generated,a.out)
