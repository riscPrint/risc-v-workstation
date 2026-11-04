"""Bounded BOOM MMIO FENCE campaign at accepted external TileLink handshakes.

The endpoint is BoomMemoryAgent's uncached sparse device window. It acknowledges
requests without an independent device execution queue. This checks I/O order
at that port only. It does not check R/W classes, caches or physical devices.
"""
import argparse
import json
from pathlib import Path
import sys

from rvw.common.proc import run_group
from rvw.results import load_run

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/ordering'))
from suite import program
from bus_observer import observe
from observer import check


def campaign():
    body, accesses, edges = [], [], []
    for case, (pred, succ) in enumerate((('i','i'), ('i','o'), ('o','i'), ('o','o'))):
        ids = []
        for index, kind in enumerate((pred, succ)):
            ident = f'{case}-{index}'
            address = 0x0c000100 + case * 64 + index * 8
            ids.append(ident)
            access = {'id': ident, 'class': kind, 'address': hex(address), 'opcode': 4 if kind == 'i' else 0, 'size_log2': 2}
            body.append(f' li t0, {address}')
            if kind == 'i':
                body.append(' lw t2, 0(t0)')
            else:
                value = 37 + case * 2 + index
                body.extend((f' li t1, {value}', ' sw t1, 0(t0)'))
                access.update(data=hex(value), mask='0xf')
            accesses.append(access)
            if index == 0:
                body.append(f' fence {pred}, {succ}')
        edges.append(ids)
    body.append(' fence iorw, iorw')  # Drain the final response before tohost ends capture.
    return program('\n'.join(body)), {'boundary': 'accepted-external-tilelink', 'accesses': accesses, 'edges': edges}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    source, plan = campaign()
    (args.out / 'test.S').write_text(source)
    (args.out / 'plan.json').write_text(json.dumps(plan, indent=2))
    (args.out / 'link.ld').write_text('OUTPUT_ARCH(riscv)\nENTRY(_start)\nSECTIONS { . = 0x80000000; .text : { *(.text*) } . = ALIGN(4096); .tohost : { *(.tohost) } .data : { *(.data*) } }\n')
    elf = args.out / 'test.elf'
    build = run_group([args.gcc, '-march=rv64ima_zicsr_zifencei', '-mabi=lp64', '-nostdlib', '-nostartfiles',
                       '-Wl,--no-relax', '-T', str(args.out / 'link.ld'), str(args.out / 'test.S'), '-o', str(elf)], timeout=60, capture=True)
    if build.returncode:
        raise RuntimeError(build.stderr)
    # The launcher holds boom and sbt locks. Timing is randomized by omission.
    run = run_group([str(ROOT / 'boom/run.sh'), 'run', '--elf', str(elf.resolve()), '--out', str((args.out / 'run').resolve()),
                     '--seed', str(args.seed), '--max-cycles', '20000', '--wall-timeout', '120', '--rvfi-trace', '--json'], timeout=1800, capture=True)
    (args.out / 'runtime.log').write_text((run.stdout or '') + (run.stderr or ''))
    result_path = args.out / 'run/result.json'
    result = load_run(result_path) if result_path.exists() else None
    if result is None or result.status != 'pass' or result.why_inconclusive:
        print(json.dumps({'status': 'inconclusive', 'reason': 'missing conclusive C1 pass'}))
        return 3
    rows = [json.loads(line) for line in (args.out / 'run/memory-bus.jsonl').read_text().splitlines()]
    observation = observe(plan, rows)
    verdict = check(plan, observation)
    (args.out / 'comparison.json').write_text(json.dumps({'observation': observation, 'ordering': verdict}, indent=2))
    print(json.dumps(verdict))
    return {'consistent': 0, 'mismatch': 1, 'inconclusive': 3}[verdict['status']]


if __name__ == '__main__':
    raise SystemExit(main())
