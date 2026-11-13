"""Prepare a bounded native UART RX failure and its simulation map."""
import argparse
import json
import os
from pathlib import Path
from rvw.common.proc import run_group

p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
here=Path(__file__).resolve().parent
soc=json.loads((here.parent.parent/'live-devices.json').read_text())
uart=next(d for d in soc['devices'] if d['model']=='ns16550')
uart['rx']=[dict(cycle=1000,byte=b) for b in [65,42,66,67,68]]
(out/'sim-map.json').write_text(json.dumps(soc,indent=2)+'\n')
gcc=os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'gcc'
built=run_group(['nice','-n','10',gcc,'-march=rv32im_zicsr','-mabi=ilp32','-nostdlib',
 '-Wl,--build-id=none','-T',str(here.parent/'programs/link.ld'),str(here/'uart-rx.S'),
 '-o',str(out/'uart.elf')],capture=True,timeout=30)
if built.returncode:raise RuntimeError(built.stdout+built.stderr)
