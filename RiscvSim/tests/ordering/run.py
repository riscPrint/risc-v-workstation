"""Build ordering ELFs and validate their assertions on Spike before an optional DUT run."""
import argparse
import json
import math
from pathlib import Path
import sys

from rvw.common.proc import run_group
from rvw.results import load_run
from suite import generate, GENERATORS


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--xlen', type=int, choices=[32, 64], default=64)
    p.add_argument('--seeds', type=int, nargs='+', default=[1, 7, 23])
    p.add_argument('--suite', choices=list(GENERATORS), action='append', help='select programs; amo-fault requires PMP lock/NAPOT')
    p.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    p.add_argument('--spike', default='spike')
    p.add_argument('--linker', type=Path, help='project link script; default RAM starts at 0x80000000')
    p.add_argument('--adapter', type=Path, help='C1 run-many executable; omit for reference-only checks')
    p.add_argument('--timeout', type=float, default=120)
    args = p.parse_args()
    if args.timeout <= 0 or not math.isfinite(args.timeout):
        p.error('--timeout must be finite and positive')
    if len(set(args.seeds)) != len(args.seeds):
        p.error('seeds must be distinct')
    jobs = [j for seed in args.seeds for j in generate(args.out, args.xlen, seed, args.suite)]
    if args.adapter and any(Path(j['out']).exists() for j in jobs):
        p.error('DUT output directories exist; use a fresh --out directory')
    base_isa = f'rv{args.xlen}ima_zicsr_zifencei'
    report = {'reference': [], 'dut': 'not_run', 'ordering': 'inconclusive',
              'limitations': 'Single-hart instruction checks do not establish concurrent ordering or atomicity.'}
    args.out.mkdir(parents=True, exist_ok=True)
    for job in jobs:
        isa = base_isa + ('_zacas' if job['name'].startswith('zacas') else '')
        cmd = [args.gcc, f'-march={isa}', '-mabi=' + ('lp64' if args.xlen == 64 else 'ilp32'),
               '-nostdlib', '-nostartfiles', '-Wl,--no-relax', '-Wl,--build-id=none',
               '-T', str(args.linker or args.out / 'link.ld'), job['source'], '-o', job['elf']]
        build = run_group(cmd, timeout=args.timeout, capture=True)
        if build.returncode:
            raise RuntimeError(f'compile failed: {build.stderr}')
        ref = run_group([args.spike, '--isa=' + isa, job['elf']], timeout=args.timeout, capture=True)
        report['reference'].append({'elf': job['elf'], 'seed': job['seed'],
                                    'status': 'pass' if ref.returncode == 0 else 'error',
                                    'exit': ref.returncode})
        (args.out / (Path(job['elf']).stem + '.spike.log')).write_text((ref.stdout or '') + (ref.stderr or ''))
        if ref.returncode:
            (args.out / 'summary.json').write_text(json.dumps(report, indent=2))
            return 2
    if args.adapter:
        manifest = args.out / 'jobs.jsonl'
        manifest.write_text(''.join(json.dumps({k: j[k] for k in
            ('elf', 'out', 'seed', 'max_cycles', 'rvfi_trace')}) + '\n' for j in jobs))
        run = run_group([str(args.adapter.resolve()), 'run-many', '--manifest', str(manifest.resolve()),
                         '--jobs', '1'], timeout=args.timeout, capture=True)
        (args.out / 'dut.log').write_text((run.stdout or '') + (run.stderr or ''))
        # Do not infer individual passes from a process exit alone.
        states = []
        for job in jobs:
            result = Path(job['out']) / 'result.json'
            if result.exists():
                loaded = load_run(result)
                states.append('inconclusive' if loaded.why_inconclusive else loaded.status)
            else:
                states.append('inconclusive')
        report['dut'] = states
        code = (1 if any(s in ('fail', 'assert', 'rvfi_error') for s in states) else
                0 if run.returncode == 0 and all(s == 'pass' for s in states) else 3)
    else:
        code = 0
    (args.out / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
