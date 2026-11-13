"""Native IRQ fixture. python Uvm/vip/interrupt/smoke.py --out NEW_DIRECTORY.

Build timeout is 120 seconds. This is not part of the default fast set.
"""
import argparse
from pathlib import Path
import urllib.request
from rvw.common.proc import run_group
from rvw.sim.uvm import unpack, URL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--verilator', default='verilator')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(exist_ok=False, parents=True)
    archive = args.archive
    if archive is None:
        archive = out / 'uvm.tar.gz'
        urllib.request.urlretrieve(URL, archive)
    lib = unpack(archive, out / 'library')
    src = Path(__file__).resolve().parent
    cmd = [args.verilator, '--binary', '--timing', '--assert', '--coverage',
           '-Wno-fatal', '-j', '2', '--top-module', 'top', '+define+UVM_NO_DPI',
           f'+incdir+{lib / "src"}', str(lib / 'src/uvm_pkg.sv'),
           *[str(src / name) for name in ('interrupt_if.sv', 'interrupt_pkg.sv', 'fixture.sv', 'test.sv')],
           '--Mdir', str(out / 'build')]
    with (out / 'build.log').open('w') as log:
        result = run_group(cmd, stdout=log, stderr=log, timeout=120)
    if result.returncode or result.timed_out:
        raise SystemExit(f'IRQ build failed: {out / "build.log"}')
    for seed in (1, 2, 3):
        for fault, diagnostic in (('', 'RVW_IRQ_DONE'), ('buggy', 'IRQ_LEVEL_OR_TIMING')):
            cmd = [str(out / 'build/Vtop'), f'+verilator+seed+{seed}']
            if fault:
                cmd.append(f'+{fault}')
            with (out / f'{seed}-{fault or "good"}.log').open('w') as log:
                result = run_group(cmd, cwd=out, stdout=log, stderr=log, timeout=10)
            text = (out / f'{seed}-{fault or "good"}.log').read_text()
            assert not result.timed_out and diagnostic in text, text
            negative = fault == 'buggy'
            assert (result.returncode != 0) == negative, text
            assert ('RVW_IRQ_DONE' in text) != negative, text
            if not negative:
                assert 'UVM_ERROR :    0' in text and 'UVM_FATAL :    0' in text, text
    print('IRQ native: 3 good runs and 3 expected diagnostic failures')


if __name__ == '__main__':
    main()
