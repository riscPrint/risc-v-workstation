"""Build reset and payload inputs for the VexiiRiscv supervisor example."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from rvw.common.proc import run_group


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--firmware',type=Path,required=True)
    p.add_argument('--kernel',type=Path)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    here=Path(__file__).resolve().parent
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    linux=a.kernel is not None
    ram=0x8000000 if linux else 0x1000000
    dtb=0x87e00000 if linux else 0x80f00000
    reset=here.joinpath('reset.S').read_text().replace('0x80f00000',hex(dtb))
    (out/'reset.S').write_text(reset)
    dts=here.joinpath('soc.dts').read_text()
    if linux:
        dts=dts.replace('/dts-v1/;', '/dts-v1/;\n/memreserve/ 0x80000000 0x00400000;')
        dts=dts.replace('0x01000000','0x08000000').replace('rv64ima_zicsr','rv64imac_zicsr')
        dts=dts.replace('chosen {', 'chosen { bootargs = "console=ttyS0,115200 earlycon=uart8250,mmio,0x10000000 keep_bootcon loglevel=8";')
    (out/'soc.dts').write_text(dts)
    def command(argv):
        r=run_group(argv,timeout=30,capture=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    gcc=shutil.which('riscv64-unknown-elf-gcc')
    if gcc is None:raise ValueError('RISC-V GCC required')
    flags=[gcc,'-march=rv64ima_zicsr_zifencei','-mabi=lp64','-nostdlib','-Wl,--build-id=none']
    command([*flags,'-T',str(here/'reset.ld'),str(out/'reset.S'),'-o',str(out/'reset.elf')])
    command(['dtc','-I','dts','-O','dtb',str(out/'soc.dts'),'-o',str(out/'soc.dtb')])
    shutil.copyfile(a.firmware,out/'firmware.bin')
    if linux:shutil.copyfile(a.kernel,out/'payload.bin')
    else:
        command([*flags,'-Ttext=0x80400000',str(here/'payload.S'),'-o',str(out/'payload.elf')])
        command([gcc.removesuffix('gcc')+'objcopy','-O','binary',str(out/'payload.elf'),str(out/'payload.bin')])
    manifest=dict(schema='rvw.boot-payloads/1',ram=[dict(base='0x80000000',size=hex(ram))],
        payloads=[dict(file='firmware.bin',address='0x80200000'),dict(file='payload.bin',address='0x80400000'),dict(file='soc.dtb',address=hex(dtb))])
    (out/'payloads.json').write_text(json.dumps(manifest,indent=2)+'\n')
    live=json.loads(here.parent.joinpath('live-devices.json').read_text())
    live['address_bits']=64;live['regions'][0]['size']=hex(ram)
    live['devices'][0]['rx']=[];live['devices'][1]['cycles_per_tick']=1
    (out/'devices.json').write_text(json.dumps(live,indent=2)+'\n')
    identities={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('firmware.bin','payload.bin','soc.dtb','reset.elf')}
    (out/'inputs.json').write_text(json.dumps(dict(schema='rvw.vexii-boot-inputs/1',linux=linux,sha256=identities),indent=2)+'\n')
    print(json.dumps(identities))

if __name__=='__main__':main()
