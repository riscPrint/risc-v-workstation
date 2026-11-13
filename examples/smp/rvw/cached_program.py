#!/usr/bin/env python3
"""Compile the fixed cached handoff at its one-MiB RAM addresses."""
import argparse,hashlib,json
from pathlib import Path
from rvw.common.proc import run_group

def build(out,gcc='riscv64-unknown-elf-gcc'):
    root=Path(out).resolve();root.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).with_name('programs')/'cached-handoff.S'
    ld=root/'shared.ld';elf=root/'shared.elf'
    ld.write_text('''ENTRY(_start)
PHDRS { ram PT_LOAD FLAGS(7); }
SECTIONS { . = 0x80000000;
.text : { *(.text*) } :ram
.tohost : { *(.tohost*) } :ram
. = 0x80080000;
.shared (NOLOAD) : { *(.shared*) } :ram
}
''')
    result=run_group(['nice','-n','10',gcc,'-march=rv64ima_zicsr_zifencei','-mabi=lp64','-nostdlib','-nostartfiles',
                    '-Wl,--no-relax','-Wl,--build-id=none','-T',str(ld),str(source),'-o',str(elf)],capture=True,timeout=30)
    if result.returncode or result.timed_out:raise ValueError(result.stdout+result.stderr)
    (root/'program.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),data_address='0x80080000',
        expected_writes={'0':37,'1':85},scope='two-way shared-line handoff; flags on a separate line'),indent=2)+'\n')
    return elf
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();print(build(a.out))
