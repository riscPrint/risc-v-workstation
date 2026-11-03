"""Generate portable, self-checking RV32/RV64 single-hart ordering programs."""
import argparse
import json
from pathlib import Path
import random

LINK = """OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS { . = 0x80000000; .text : { *(.text*) }
. = ALIGN(4096); .tohost : { *(.tohost) }
.data : { *(.data*) } }
"""


def program(body, data="", *, xlen=64):
    store = 'sd' if xlen == 64 else 'sw'
    return f""".option norvc
.section .text
.globl _start
_start:
 la t0, fail
 csrw mtvec, t0
{body}
 li a0, 1
 j finish
fail:
 li a0, 3
finish:
 la t0, tohost
 {store} a0, 0(t0)
1: j 1b
.section .tohost, "aw"
.balign 8
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
.section .data
.balign 64
cell: .dword 0
other: .dword 0
{data}
"""


def lrsc(xlen, seed):
    # SC may fail spuriously. Only a successful SC must update the bytes.
    bodies = []
    for width in (['w', 'd'] if xlen == 64 else ['w']):
        for suffix in ['', '.aq', '.rl', '.aqrl']:
            bodies.append(f"""la t0, cell
 sw zero, 0(t0)
 li t1, 37
 sc.{width}{suffix} t2, t1, (t0)
 beqz t2, fail
 l{width} t3, 0(t0)
 bnez t3, fail
 lr.{width}{suffix} t2, (t0)
 sc.{width}{suffix} t2, t1, (t0)
 l{width} t3, 0(t0)
 bnez t2, 2f
 bne t3, t1, fail
 j 3f
2: bnez t3, fail
3:
 lr.{width} t2, (t0)
 la t4, other
 sc.{width} t2, t1, (t4)
 beqz t2, fail
 l{width} t3, 0(t4)
 bnez t3, fail
""")
    return program('\n'.join(bodies), xlen=xlen)


def generate(out, xlen=64, seed=1, suites=('lrsc',)):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'link.ld').write_text(LINK)
    jobs = []
    for name in suites:
        source = out / f'{name}-{seed}.S'
        source.write_text(GENERATORS[name](xlen, seed))
        jobs.append(dict(name=name, seed=seed, xlen=xlen, source=str(source.resolve()),
                         elf=str(source.with_suffix('.elf').resolve()),
                         # Omit mem_latency: the C1 adapter must randomize timing.
                         out=str((out / f'{name}-{seed}-run').resolve()),
                         max_cycles=200000, rvfi_trace=True))
    (out / f'manifest-{seed}.jsonl').write_text(''.join(json.dumps({k: j[k] for k in
        ('elf', 'out', 'seed', 'max_cycles', 'rvfi_trace')}) + '\n' for j in jobs))
    return jobs


GENERATORS = {'lrsc': lrsc}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--xlen', type=int, choices=[32, 64], default=64)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--suite', choices=list(GENERATORS), action='append')
    args = parser.parse_args()
    print(json.dumps(generate(args.out, args.xlen, args.seed, args.suite or tuple(GENERATORS)), indent=2))


if __name__ == '__main__':
    main()
