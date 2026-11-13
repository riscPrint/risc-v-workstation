#!/usr/bin/env python3
"""Project recipe: rvw soc memory map plus explicit Linux bindings, native QEMU."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from rvw.common.proc import run_group
from rvw.soc.model import generate, load
from rvw.arch.linux import minimal_initramfs


def tree(source, out):
    generate(source, out)
    data = load(source)
    regions = {r['name']: r for r in data['regions']}
    def reg(name):
        r = regions[name]
        return f'<0 {r["base"]:#x} 0 {r["size"]:#x}>'
    extra = '''
  chosen { stdout-path = "/soc/serial@10000000"; };
  cpus {
    #address-cells = <1>; #size-cells = <0>; timebase-frequency = <10000000>;
    cpu@0 {
      device_type = "cpu"; reg = <0>; status = "okay";
      compatible = "riscv"; riscv,isa = "rv64imafdc_zicsr_zifencei";
      mmu-type = "riscv,sv39";
      intc: interrupt-controller { #interrupt-cells = <1>;
        interrupt-controller; compatible = "riscv,cpu-intc"; };
    };
  };
  poweroff { compatible = "syscon-poweroff"; regmap = <&test>;
    offset = <0>; value = <0x5555>; };
  soc {
    #address-cells = <2>; #size-cells = <2>;
    compatible = "simple-bus"; ranges;
    test: test@100000 { compatible = "sifive,test1", "sifive,test0", "syscon";
      reg = TEST_REG; };
    serial@10000000 {
      compatible = "ns16550a"; reg = UART_REG;
      clock-frequency = <3686400>; interrupt-parent = <&plic>; interrupts = <10>;
    };
    clint@2000000 {
      compatible = "riscv,clint0"; reg = CLINT_REG;
      interrupts-extended = <&intc 3 &intc 7>;
    };
    plic: interrupt-controller@c000000 {
      compatible = "riscv,plic0"; reg = PLIC_REG;
      #interrupt-cells = <1>; interrupt-controller; riscv,ndev = <95>;
      interrupts-extended = <&intc 11 &intc 9>;
    };
  };
'''
    # The node paths are fixed by this project binding. Refuse a moved device.
    for name, base in [('uart', 0x10000000), ('clint', 0x2000000), ('plic', 0xc000000), ('test', 0x100000)]:
        if regions[name]['base'] != base:
            raise ValueError('update the project Linux binding when moving a device')
        extra = extra.replace(name.upper() + '_REG', reg(name))
    path = out / 'soc.dts'
    path.write_text(path.read_text().replace('/ {', '/ { compatible = \"rvw,sim-linux\"; model = \"rvw map reference\";', 1).rsplit('};', 1)[0] + extra + '};\n')
    result = run_group(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(out/'soc.dtb'), str(path)], timeout=20, capture=True)
    if result.returncode: raise ValueError(result.stderr)


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--soc', type=Path, default=Path(__file__).with_name('sim-soc.json'))
    p.add_argument('--images', required=True, type=Path, help='hash-checked prebuilt Image and installer rootfs.cpio.gz')
    p.add_argument('--firmware', required=True, type=Path, help='OpenSBI fw_dynamic binary')
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    args.out = args.out.resolve()
    tree(args.soc, args.out)
    lock = json.loads(Path(__file__).with_name('prebuilt.json').read_text())
    for name, item in lock['artifacts'].items():
        if hashlib.sha256((args.images/name).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('image digest mismatch: '+name)
    init = Path(__file__).resolve().parents[2] / 'Arch/linux/overlay/init'
    rootfs = args.out/'rootfs.cpio.gz'
    rootfs.write_bytes(minimal_initramfs((args.images/'rootfs.cpio.gz').read_bytes(), lock['initramfs_selection'], init.read_bytes()))
    qemu = shutil.which('qemu-system-riscv64')
    if not qemu: raise ValueError('missing qemu-system-riscv64')
    cmd = [qemu, '-machine', 'virt', '-m', '128M', '-smp', '1', '-nographic', '-monitor', 'none', '-nic', 'none',
        '-bios', str(args.firmware.resolve(strict=True)), '-kernel', str((args.images/'Image').resolve()), '-initrd', str(rootfs),
        '-dtb', str(args.out/'soc.dtb'), '-append', 'console=ttyS0 earlycon=sbi rdinit=/rvw-init panic=-1']
    with (args.out/'console.log').open('w') as log:
        result = run_group(['nice', '-n', '10', *cmd], timeout=120, stdout=log, stderr=log)
    console = (args.out/'console.log').read_text()
    ok = not result.timed_out and result.returncode == 0 and 'RVW_LINUX_USERSPACE_OK' in console
    files = [args.soc, args.images/'Image', rootfs, args.out/'soc.dtb', Path(qemu), args.firmware.resolve(strict=True)]
    report = dict(status='pass' if ok else 'inconclusive', argv=cmd, returncode=result.returncode,
                  timed_out=result.timed_out, scope='QEMU userspace only; no RTL boot',
                  inputs={str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.exists()})
    (args.out/'boot.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return 0 if ok else 3

if __name__ == '__main__':
    raise SystemExit(main())
