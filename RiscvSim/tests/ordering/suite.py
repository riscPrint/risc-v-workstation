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
 s{width} zero, 0(t0)
 la t4, other
 s{width} zero, 0(t4)
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
 lr.{width} t5, (t0)
 la t4, other
 sc.{width} t2, t1, (t4)
 l{width} t3, 0(t4)
 bnez t2, 4f
 bne t3, t1, fail
 j 5f
4: bnez t3, fail
5:
 l{width} t3, 0(t0)
 bne t3, t5, fail
 # Every SC consumes the reservation, including a failed SC.
 sc.{width} t2, t1, (t0)
 beqz t2, fail
 l{width} t3, 0(t0)
 bne t3, t5, fail
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


def amo_fault(xlen, seed):
    """Opt-in PMP read-only 64-byte region; aligned AMOs must raise cause 7.

    Requires PMP with lock and NAPOT support. No policy is inferred from the DUT.
    """
    store = 'sd' if xlen == 64 else 'sw'
    bodies = [f"""la t0, cell
 li t1, 37
 {store} t1, 0(t0)
 mv s2, t0
 srli t1, t0, 2
 ori t1, t1, 7
 csrw pmpaddr0, t1
 li t1, 0x99
 csrw pmpcfg0, t1
 csrr t2, pmpcfg0
 andi t2, t2, 255
 bne t1, t2, fail
 la t1, amo_trap
 csrw mtvec, t1
 li s1, 0
"""]
    index = 0
    for width in (['w', 'd'] if xlen == 64 else ['w']):
        for suffix in ['', '.aq', '.rl', '.aqrl']:
            for op in ('swap', 'add', 'xor', 'and', 'or', 'min', 'max', 'minu', 'maxu'):
                index += 1
                bodies.append(f"""la s0, amo_fault_{index}
 li t1, 73
 li t2, 85
amo_fault_{index}:
 amo{op}.{width}{suffix} t2, t1, (t0)
 li t3, 85
 bne t2, t3, fail
 l{width} t4, 0(t0)
 li t3, 37
 bne t4, t3, fail
 li t3, {index}
 bne s1, t3, fail
 addi t4, t0, 1
 li t5, 63
check_bytes_{index}:
 lbu t6, 0(t4)
 bnez t6, fail
 addi t4, t4, 1
 addi t5, t5, -1
 bnez t5, check_bytes_{index}
""")
    handler = """
.balign 4
amo_trap:
 csrr t4, mcause
 li t5, 7
 bne t4, t5, fail
 csrr t4, mepc
 bne t4, s0, fail
 csrr t4, mtval
 bne t4, s2, fail
 addi s1, s1, 1
 addi t4, s0, 4
 csrw mepc, t4
 mret
"""
    return program('\n'.join(bodies), xlen=xlen).replace('other: .dword 0', 'other: .dword 0\n.space 48').replace('.section .tohost', handler + '\n.section .tohost')


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


def zacas(xlen, seed):
    """Opt-in Zacas integer effects, including the double-XLEN register pair."""
    rng = random.Random(seed)
    bodies = []
    for width in ([4, 8] if xlen == 32 else [4, 8, 16]):
        bits = width * 8
        unit = min(width, xlen // 8)
        load, store = ('lw', 'sw') if unit == 4 else ('ld', 'sd')
        mask = (1 << bits) - 1
        def chunks(value):
            return [(value >> shift) & ((1 << (unit*8))-1) for shift in range(0, bits, unit*8)]
        def initialize(value):
            return '\n'.join(f' li t1, {v}\n {store} t1, {i*unit}(a0)' for i,v in enumerate(chunks(value)))
        def registers(base, value):
            return '\n'.join(f' li x{base+i}, {v}' for i,v in enumerate(chunks(value)))
        def returned(value, rd=12):
            if rd == 0:
                return ' li t1, 91\n bne ra, t1, fail'
            values = chunks(value)
            if width == 4 and xlen == 64 and value & (1 << 31):
                values = [value - (1 << 32)]
            return '\n'.join(f' li t1, {v}\n bne x{rd+i}, t1, fail' for i,v in enumerate(values))
        def memory(value):
            lines = []
            for i, v in enumerate(chunks(value)):
                # LW sign extends on RV64.
                if unit == 4 and xlen == 64 and v & (1 << 31):
                    v -= 1 << 32
                lines.append(f' {load} t2, {i*unit}(a0)\n li t1, {v}\n bne t2, t1, fail')
            return '\n'.join(lines)
        for flags in range(4):
            funct7 = (5 << 2) | flags
            funct3 = {4: 2, 8: 3, 16: 4}[width]
            vectors = [(1 << (bits-1), mask), (rng.getrandbits(bits), rng.getrandbits(bits))]
            for old, new in vectors:
                for success in [True, False]:
                    compare = old if success else old ^ 1
                    bodies.append(f"""la a0, cell
{initialize(old)}
 li t1, 0xa5
 sb t1, -1(a0)
 sb t1, {width}(a0)
{registers(12, compare)}
{registers(14, new)}
 .insn r 0x2f, {funct3}, {funct7}, a2, a0, a4
{returned(old)}
{memory(new if success else old)}
 lbu t2, -1(a0)
 li t1, 0xa5
 bne t2, t1, fail
 lbu t2, {width}(a0)
 bne t2, t1, fail
""")
            # x0 pair reads both halves as zero and discards both destinations.
            # Keep x1 nonzero to detect accidental use or modification of it.
            for rd, rs2, old, new in [(0,14,0,73), (12,0,37,0)]:
                bodies.append(f"""la a0, cell
{initialize(old)}
{registers(12, old)}
{registers(14, new)}
 li ra, 91
 .insn r 0x2f, {funct3}, {funct7}, x{rd}, a0, x{rs2}
{returned(old, rd)}
{memory(new)}
 li t1, 91
 bne ra, t1, fail
""")
    return program('\n'.join(bodies), xlen=xlen).replace('cell: .dword 0', '.dword 0\n.balign 64\ncell: .dword 0\n.dword 0\n.dword 0')


def zacas_traps(xlen, seed, protection=True):
    """Explicit PMP read-only or natural-alignment-only profile."""
    body = ["""la t0, cell
 li t1, 37
 sw t1, 0(t0)
 la t1, cas_trap
 csrw mtvec, t1
 li s1, 0
"""]
    if protection:
        body.append("""srli t1, t0, 2
 ori t1, t1, 7
 csrw pmpaddr0, t1
 li t1, 0x99
 csrw pmpcfg0, t1
 csrr t2, pmpcfg0
 andi t2, t2, 255
 bne t1, t2, fail
""")
    index = 0
    for width in ([4,8] if xlen == 32 else [4,8,16]):
        for flags in range(4):
            index += 1
            body.append(f"""la a0, cell
 addi a0, a0, {0 if protection else 1}
 la s0, cas_fault_{index}
 li a2, 85
 li a3, 102
 li a4, 73
 li a5, 74
cas_fault_{index}:
 .insn r 0x2f, { {4:2,8:3,16:4}[width]}, {20+flags}, a2, a0, a4
 li t1, 85
 bne a2, t1, fail
 li t1, 102
 bne a3, t1, fail
 li t1, {index}
 bne s1, t1, fail
 la t4, cell
 lbu t5, 0(t4)
 li t1, 37
 bne t5, t1, fail
 addi t4, t4, 1
 li t5, 63
cas_bytes_{index}:
 lbu t6, 0(t4)
 bnez t6, fail
 addi t4, t4, 1
 addi t5, t5, -1
 bnez t5, cas_bytes_{index}
""")
    cause = ' li t5, 7\n bne t4, t5, fail' if protection else ' li t5, 6\n beq t4, t5, cas_cause_ok\n li t5, 7\n bne t4, t5, fail\ncas_cause_ok:'
    handler = f"""
.balign 4
cas_trap:
 csrr t4, mcause
{cause}
 csrr t4, mepc
 bne t4, s0, fail
 csrr t4, mtval
 bne t4, a0, fail
 addi s1, s1, 1
 addi t4, s0, 4
 csrw mepc, t4
 mret
"""
    return program('\n'.join(body), xlen=xlen).replace('other: .dword 0', 'other: .dword 0\n.space 48').replace('.section .tohost', handler+'\n.section .tohost')


def generate(out, xlen=64, seed=1, suites=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'link.ld').write_text(LINK)
    jobs = []
    for name in (DEFAULT_SUITES if suites is None else suites):
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


DEFAULT_SUITES = ('lrsc', 'amo', 'fence', 'fence-i')
GENERATORS = {'zacas': zacas, 'zacas-fault': zacas_traps,
              'zacas-align': lambda xlen, seed: zacas_traps(xlen, seed, False), 'amo-fault': amo_fault, 'lrsc': lrsc, 'amo': amo, 'fence': fence, 'fence-i': fence_i}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--xlen', type=int, choices=[32, 64], default=64)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--suite', choices=list(GENERATORS), action='append')
    args = parser.parse_args()
    print(json.dumps(generate(args.out, args.xlen, args.seed, args.suite or DEFAULT_SUITES), indent=2))


if __name__ == '__main__':
    main()
