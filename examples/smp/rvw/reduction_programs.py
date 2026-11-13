"""Build checked pass/fail controls for private per-hart instruction reduction."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from programs import assembly,build
from rvw.runs.elf import Elf
from rvw.reduce.streams import instruction_slots


def source(hart,keep=True):
    code=assembly(hart,'smoke')
    body='\n'.join(['addi s4,zero,123','addi s3,s3,1','addi s5,zero,456'] if keep else ['nop']*3)
    region='li s3,0\n.global fault_region\n.type fault_region,@function\nfault_region:\n'+body+'''
.size fault_region,.-fault_region
beqz s3,good
li a0,15
j finish
good:
li a0,1
j finish'''
    return code.replace('li a0, 1\nj finish',region)


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();root=a.out.resolve();root.mkdir(parents=True,exist_ok=False)
    build(root/'original',sources=[assembly(0,'smoke'),source(1)])
    original=Elf(str(root/'original/hart-1.elf'));slots=instruction_slots(original,'fault_region')
    for name,kept in [('reduced',[1]),('empty',[])]:
        out=root/name;shutil.copytree(root/'original',out)
        image=Elf(str(out/'hart-1.elf'))
        for i,(offset,size) in enumerate(slots):
            if i not in kept:image.data[offset:offset+size]=bytes.fromhex('13000000')
        image.save(str(out/'hart-1.elf'))
        data=json.loads((out/'hart-images.json').read_text())
        for row in data['harts']:
            elf=out/f"hart-{row['hart']}.elf"
            row.update(elf=str(elf),elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())
        (out/'hart-images.json').write_text(json.dumps(data,indent=2)+'\n')
    build(root/'wrong-hart',sources=[source(0),source(1,False)])
    print(root)

if __name__=='__main__':main()
