#!/usr/bin/env python3
"""Compile only the six pinned ordering litmus cases for the SMP example."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from rvw.memory.multihart import images

ROOT = Path(__file__).resolve().parents[3]
PINS = json.loads((ROOT/'RiscvSim/tests/ordering/litmus-pins.json').read_text())


def parse(test):
    test = Path(test)
    digest = hashlib.sha256(test.read_bytes()).hexdigest()
    if digest not in PINS['cases'].values():
        raise ValueError('only pinned litmus bytes are supported')
    text = test.read_text()
    initial = re.search(r'\{(.*?)\}',text,re.S).group(1)
    regs = [{}, {}]
    for h,r,value in re.findall(r'(\d+):x(\d+)=(x|y|\d+)\s*;',initial):
        if int(h)>1 or not 1<=int(r)<=29:
            raise ValueError('unsupported initial register')
        regs[int(h)][int(r)] = {'x':0x81000000,'y':0x81000040}.get(value,int(value) if value.isdecimal() else None)
    table = text.split('}',1)[1].split('exists',1)[0].strip().splitlines()
    if not re.fullmatch(r'\s*P0\s*\|\s*P1\s*;',table[0]):
        raise ValueError('two-hart instruction table required')
    instructions = [[],[]]
    for row in table[1:]:
        columns = row.strip().removesuffix(';').split('|')
        if len(columns)!=2:
            raise ValueError('two instruction columns required')
        for h,instruction in enumerate(columns):
            instruction=instruction.strip()
            if not re.fullmatch(r'(?:lw|sw) x(?:[1-9]|[12][0-9]),0\(x(?:[1-9]|[12][0-9])\)|fence rw,rw',instruction):
                raise ValueError('unsupported litmus instruction')
            instructions[h].append(instruction)
    projection = sorted(set(re.findall(r'\b[01]:x\d+\b',text.split('exists',1)[1])))
    return regs,instructions,projection,digest


def build(test,out,gcc='riscv64-unknown-elf-gcc'):
    regs,instructions,projection,digest=parse(test)
    root=Path(out).resolve(); root.mkdir(parents=True,exist_ok=False)
    inputs=[]
    for h in range(2):
        lines=['.option norvc','.text','.globl _start','_start:']
        lines += [f'li x{r}, {v}' for r,v in sorted(regs[h].items())]
        lines += instructions[h]
        lines += ['la x30, tohost','li x31, 1','sd x31, 0(x30)','park: j park',
                  '.section .tohost,"aw",@progbits','.balign 64','.globl tohost','tohost: .dword 0',
                  '.section .shared,"aw",@nobits','.zero 128']
        source,link,elf=[root/f'hart-{h}{s}' for s in ['.S','.ld','.elf']]
        source.write_text('\n'.join(lines)+'\n')
        link.write_text(f'''ENTRY(_start)
PHDRS {{ private PT_LOAD FLAGS(7); shared PT_LOAD FLAGS(6); }}
SECTIONS {{ . = {0x80000000+h*0x20000};
.text : {{ *(.text*) }} :private
.tohost : {{ *(.tohost*) }} :private
. = 0x81000000;
.shared (NOLOAD) : {{ *(.shared*) }} :shared
}}
''')
        subprocess.run(['nice','-n','10',gcc,'-march=rv64ima_zicsr_zifencei','-mabi=lp64','-nostdlib','-nostartfiles',
                        '-Wl,--no-relax','-Wl,--build-id=none','-T',str(link),str(source),'-o',str(elf)],
                       check=True,timeout=30)
        inputs.append(f'{h}={elf}')
    (root/'hart-images.json').write_text(json.dumps(images(inputs),indent=2)+'\n')
    (root/'litmus.json').write_text(json.dumps(dict(test=Path(test).name,test_sha256=digest,
                                                  projection=projection),indent=2)+'\n')
    return root/'hart-images.json'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('test');p.add_argument('--out',required=True)
    a=p.parse_args();print(build(a.test,a.out))
