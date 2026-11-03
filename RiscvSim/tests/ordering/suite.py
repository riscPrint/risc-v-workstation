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


def amo(xlen, seed):
    rng = random.Random(seed)
    bodies = []
    ops = ('swap', 'add', 'xor', 'and', 'or', 'min', 'max', 'minu', 'maxu')
    for width in (['w', 'd'] if xlen == 64 else ['w']):
        bits = 32 if width == 'w' else 64
        mask = (1 << bits) - 1
        signed = lambda n: n - (1 << bits) if n >> (bits - 1) else n
        for suffix in ['', '.aq', '.rl', '.aqrl']:
            for op in ops:
                # The first vector tests signed extrema. The second is random.
                for a, b in [(1 << (bits-1), mask), (rng.getrandbits(bits), rng.getrandbits(bits))]:
                    result = {'swap': b, 'add': (a+b) & mask, 'xor': a^b,
                              'and': a&b, 'or': a|b, 'min': min(a,b,key=signed),
                              'max': max(a,b,key=signed), 'minu': min(a,b), 'maxu': max(a,b)}[op]
                    # LW and AMO.W return a sign-extended value on RV64.
                    old = signed(a) if bits == 32 and xlen == 64 else a
                    new = signed(result) if bits == 32 and xlen == 64 else result
                    bodies.append(f"""la t0, cell
 li t1, 0xa5
 sb t1, -1(t0)
 sb t1, {bits//8}(t0)
 li t1, {a}
 s{width} t1, 0(t0)
 li t1, {b}
 amo{op}.{width}{suffix} t2, t1, (t0)
 li t3, {old}
 bne t2, t3, fail
 l{width} t2, 0(t0)
 li t3, {new}
 bne t2, t3, fail
 lbu t2, -1(t0)
 li t3, 0xa5
 bne t2, t3, fail
 lbu t2, {bits//8}(t0)
 bne t2, t3, fail
""")
    return program('\n'.join(bodies), xlen=xlen).replace('cell: .dword 0', '.dword 0\ncell: .dword 0')


def fence(xlen, seed):
    rng = random.Random(seed)
    classes = ['r', 'w', 'rw', 'i', 'o', 'io', 'iorw']
    pairs = [(p, s) for p in classes for s in classes]
    rng.shuffle(pairs)
    bodies = []
    for pred, succ in pairs:
        value = rng.randrange(1, 1 << 20)
        bodies.append(f"""la t0, cell
 li t1, {value}
 sw t1, 0(t0)
 fence {pred}, {succ}
 lw t2, 0(t0)
 bne t1, t2, fail
""")
    return program('\n'.join(bodies), xlen=xlen)


def fence_i(xlen, seed):
    rng = random.Random(seed)
    bodies, functions = [], []
    for index, offset in enumerate([0, 60, 124]):
        bodies.append(f"""la s0, patch{index}
 jalr ra, s0, 0
 li t1, 1
 bne a1, t1, fail
""")
        for _ in range(8):
            value = rng.randrange(2, 2048)
            instruction = (value << 20) | (11 << 7) | 0x13  # addi a1, zero, imm
            bodies.append(f"""li t1, {instruction}
 sw t1, 0(s0)
 fence.i
 jalr ra, s0, 0
 li t1, {value}
 bne a1, t1, fail
""")
        functions.append(f""".balign 128
 .space {offset}
patch{index}:
 addi a1, zero, 1
 ret
""")
    text = program('\n'.join(bodies), xlen=xlen)
    return text.replace('.section .tohost', '\n'.join(functions) + '\n.section .tohost')


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


GENERATORS = {'lrsc': lrsc, 'amo': amo, 'fence': fence, 'fence-i': fence_i}


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
