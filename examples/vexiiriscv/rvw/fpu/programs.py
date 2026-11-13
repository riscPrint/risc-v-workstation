#!/usr/bin/env python3
"""Write directed FP class programs. Spike supplies the arithmetic oracle."""
import argparse
import random
from pathlib import Path

VALUES = {32: [0, 1, 0x3f800000, 0x7f800000, 0x7fc00000, 0x7f800001],
          64: [0, 1, 0x3ff0000000000000, 0x7ff0000000000000, 0x7ff8000000000000, 0x7ff0000000000001]}
RMS = ['rne', 'rtz', 'rdn', 'rup', 'rmm']


def envelope(body, data=''):
    return '''.section .text.init
.globl _start
.option norvc
_start:
  la t0, trap
  csrw mtvec, t0
  li t0, 0x6000
  csrs mstatus, t0
''' + body + '''
pass:
  li t0, 1
  j finish
fail:
  li t0, 3
finish:
  la t1, tohost
  sw t0, 0(t1)
  j finish
trap:
  j fail
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
.section .data
.balign 8
''' + data


def arithmetic(width, seed, random_cases):
    rng = random.Random(seed)
    suffix, load, datum = ('s', 'flw', '.word') if width == 32 else ('d', 'fld', '.dword')
    values = VALUES[width]
    cases = [(a, b) for a in values for b in values]
    cases += [(rng.getrandbits(width), rng.getrandbits(width)) for _ in range(random_cases)]
    body, data = [], []
    for i, (a, b) in enumerate(cases):
        data += [f'a{i}: {datum} 0x{a:x}', f'b{i}: {datum} 0x{b:x}']
        body += [f'  la t0, a{i}', f'  {load} f1, 0(t0)', f'  la t0, b{i}', f'  {load} f2, 0(t0)']
        for rm in RMS:
            for op in ['fadd', 'fsub', 'fmul', 'fdiv', 'fsqrt']:
                operands = 'f1' if op == 'fsqrt' else 'f1, f2'
                body += ['  csrw fcsr, zero', f'  {op}.{suffix} f0, {operands}, {rm}', '  frflags t2']
    return envelope('\n'.join(body), '\n'.join(data))




def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--width', type=int, choices=[32, 64], required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--random-cases', type=int, default=16)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'classes.S').write_text(arithmetic(args.width, args.seed, args.random_cases))

if __name__ == '__main__':
    main()
