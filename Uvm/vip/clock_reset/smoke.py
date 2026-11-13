"""Native CLOCK_RESET fixture. python Uvm/vip/clock_reset/smoke.py --out NEW_DIRECTORY.

Build timeout is 120 seconds. This is not part of the default fast set.
"""
import argparse
from pathlib import Path
import urllib.request
from rvw.common.proc import run_group
from rvw.sim.uvm import unpack, URL, require_evidence


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
           *[str(src / name) for name in ('clock_reset_if.sv', 'clock_reset_pkg.sv', 'fixture.sv', 'test.sv')],
           '--Mdir', str(out / 'build')]
    with (out / 'build.log').open('w') as log:
        result = run_group(cmd, stdout=log, stderr=log, timeout=120)
    if result.returncode or result.timed_out:
        raise SystemExit(f'CLOCK_RESET build failed: {out / "build.log"}')
    for seed in (1, 2, 3):
        for fault, diagnostic in (('', 'RVW_CLOCK_RESET_DONE'), ('buggy', 'RESET_RELEASE_EDGE')):
            cmd = [str(out / 'build/Vtop'), f'+verilator+seed+{seed}']
            if fault:
                cmd.append(f'+{fault}')
            with (out / f'{seed}-{fault or "good"}.log').open('w') as log:
                result = run_group(cmd, cwd=out, stdout=log, stderr=log, timeout=10)
            text = (out / f'{seed}-{fault or "good"}.log').read_text()
            require_evidence(not result.timed_out and diagnostic in text, text)
            negative = fault == 'buggy'
            require_evidence((result.returncode != 0) == negative, text)
            require_evidence(('RVW_CLOCK_RESET_DONE' in text) != negative, text)
            if not negative:
                require_evidence('UVM_ERROR :    0' in text and 'UVM_FATAL :    0' in text, text)
    print('CLOCK_RESET native: 3 good runs and 3 expected diagnostic failures')


if __name__ == '__main__':
    main()
