#!/usr/bin/env python3
"""Prepare isolated project adapters and native reduction programs."""
import argparse
from pathlib import Path
import os
import shutil
from rvw.common.proc import run_group


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--rtl',type=Path,required=True)
    args=p.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent;harness=out/'harness';harness.mkdir()
    for name in ('driver.py','run.sh'):shutil.copyfile(here/name,harness/name)
    (harness/'run.sh').chmod(0o755)
    shutil.copyfile(here.parent/'engine-probe.py',harness/'engine_probe.py')
    shutil.copyfile(here.parent/'engine-ports.json',harness/'engine-ports.json')
    shutil.copyfile(args.rtl,harness/'VexTop.v')
    # A private VexRiscv checkout ignores all JSON files. C8 needs these assets.
    (harness/'.gitignore').write_text('!engine-ports.json\n!VexTop.v\n__pycache__/\n')
    (harness/'debug.toml').write_text('[core]\nsource_env="VEXRISCV"\n')
    gcc=os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'gcc'
    for name in ('instructions','interrupts'):
        r=run_group([gcc,'-march=rv32im_zicsr_zifencei','-mabi=ilp32','-nostdlib','-nostartfiles',
            '-T',str(here.parent/'programs/link.ld'),str(here/(name+'.S')),'-o',str(out/(name+'.elf'))],timeout=30,capture=True)
        if r.returncode:raise ValueError(r.stderr)
    print(out)

if __name__=='__main__':main()
