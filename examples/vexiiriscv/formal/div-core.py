#!/usr/bin/env python3
"""Build rv32um divide tests and replay core commits with Spike.

Set VEXIIRISCV to a private pinned source copy. All build output stays in
this checkout or --out. Runs use the private vex-equiv and sbt-equiv locks.
"""
import argparse
import json
import os
from pathlib import Path
from rvw.common.proc import run_group


def compile_command(gcc, tests, name, elf):
    return [gcc, '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-nostdlib', '-nostartfiles',
            '-I' + str(tests / 'env/p'), '-I' + str(tests / 'isa/macros/scalar'),
            '-T' + str(tests / 'env/p/link.ld'), str(tests / 'isa/rv32um' / (name + '.S')),
            '-o', str(elf)]


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--tests', type=Path, required=True, help='external pinned riscv-tests checkout')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    p.add_argument('--config', choices=['rv32im', 'rv32im_bitpasta', 'rv32im_bitpasta_ipc'], default='rv32im_bitpasta_ipc')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[3]
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, RVW_HOME=str(root), RVW_VEX_LOCK='vex-equiv',
               RVW_SBT_LOCK='sbt-equiv', RISCVSIM_WORK=str(out / 'sim'))
    jobs = []
    for name in ('div', 'divu', 'rem', 'remu'):
        elf = out / name
        r = run_group(['nice', '-n', '10', *compile_command(a.gcc, a.tests.resolve(), name, elf)], timeout=30, capture=True)
        (out / (name + '-build.log')).write_text((r.stdout or '') + (r.stderr or ''))
        if r.returncode: return 3
        jobs.append(dict(elf=str(elf), out=str(out / (name + '-run')), config=a.config,
                         max_cycles=10000, seed=1, rvfi_trace=True, mem_latency=0))
    manifest = out / 'jobs.jsonl'
    manifest.write_text(''.join(json.dumps(j) + '\n' for j in jobs))
    r = run_group(['nice', '-n', '10', str(root / 'examples/vexiiriscv/rvw/run.sh'),
                   'run-many', '--manifest', str(manifest), '--jobs', '1', '--json'],
                  env=env, timeout=120, capture=True)
    (out / 'core.log').write_text((r.stdout or '') + (r.stderr or ''))
    results = []
    for job in jobs:
        report = Path(job['out']) / 'result.json'
        result = json.loads(report.read_text()) if report.exists() else {'status': 'inconclusive'}
        r = run_group(['nice', '-n', '10', str(root / 'rvw/.venv/bin/rvw'), 'cosim', 'check',
                       '--core', 'vexiiriscv', '--platform', str(root / 'examples/vexiiriscv/rvw/platform.json'),
                       '--elf', job['elf'], '--trace', str(Path(job['out']) / 'rvfi.jsonl'), '--json'],
                      env=env, timeout=30, capture=True)
        try: compared = json.loads(r.stdout)
        except (ValueError, TypeError): compared = {'status': 'inconclusive'}
        results.append(dict(test=Path(job['elf']).name, rtl_status=result['status'],
                            fail_code=result.get('fail_code'), spike=compared))
    (out / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
    return 0 if all(x['spike']['status'] == 'match' for x in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
